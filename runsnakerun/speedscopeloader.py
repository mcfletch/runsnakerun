"""Adapter for RunSnakeRun to load speedshot (py-spy) profiles"""
from __future__ import absolute_import
import sys, os, logging

log = logging.getLogger(__name__)

SSP_SHARED = "shared"
SSP_PROFILES = "profiles"
SSP_NAME = "name"
SSP_ACTIVE_PROFILE_INDEX = "activeProfileIndex"
SSP_TYPE_SAMPLED = "sampled"


class DataBase(object):
    def __init__(self, **named):
        for key, value in named.items():
            if not key.startswith("_"):
                setattr(self, key, value)

    def descendants(self, known=None):
        """(Recursively) Get the set of all descendants of this node"""
        known = known or set()
        for child in self.children:
            if child not in known:
                known.add(child)
                child.descendants(known)
        return list(known)

    def ancestors(self, known=None):
        """(Recursively) Get the set of all parents of this node"""
        known = known or set()
        for parent in self.parents:
            if parent not in known:
                known.add(parent)
                parent.ancestors(known)
        return list(known)


class Profile(DataBase):
    name = None
    unit = None
    startValue = 0.0
    endValue = 1.0
    frames = None  # from the overall file...


class StackFrame(DataBase):
    @property
    def parents(self):
        parent = self.profile._parent(self.path)
        if parent:
            return [parent]
        else:
            return []

    def child_cumulative_time(self, child):
        """What fraction of our cumulative time was spent in child?"""
        return child.cumulative / float(self.cumulative or 1.0)

    @property
    def name(self):
        return self.frame.name

    @property
    def filename(self):
        return os.path.basename(self.frame.file)

    @property
    def directory(self):
        return os.path.dirname(self.frame.file)

    @property
    def lineno(self):
        return self.frame.line

    @property
    def localPer(self):
        return self.local / float(self.calls or 1)

    @property
    def cumulativePer(self):
        return self.cumulative / float(self.calls or 1)


class Frame(DataBase):
    name = None
    file = None
    line = None
    index = None
    col = None
    path = None
    profile = None

    def __str__(self):
        return "%s@%s:%s" % (self.name, self.file, self.line,)

    def __repr__(self):
        return str(self)


class SampledProfile(Profile):
    type = "sampled"
    samples = None
    weights = None
    total = 0.0

    _roots = None
    _parent_map = None

    @property
    def parent_map(self):
        if self._parent_map is None:
            if self.roots:
                pass
        return self._parent_map

    @property
    def roots(self):
        if self._roots is None:
            self._roots = []
            path_map = {}

            if not self.weights:
                self.weights = [1] * len(self.samples)
            elif len(self.weights) < len(self.samples):
                self.samples += [1] * (len(self.samples) - len(self.weights))
            self.total = sum(self.weights, 0.0)
            for sample, weight in zip(self.samples, self.weights):
                if not sample:
                    continue
                parent = None
                for index, frame_index in enumerate(sample):
                    frame = self.frames[frame_index]
                    path = tuple(sample[: index + 1])
                    current = path_map.get(path)
                    local = weight if frame_index == len(sample) - 1 else 0.0
                    # weight is cumulative for all parents, but local
                    # to *only* the final element
                    if current is None:
                        current = path_map[path] = StackFrame(
                            path=path,
                            profile=self,
                            frame=frame,
                            cumulative=weight,
                            local=local,
                            calls=1,
                            children=[],
                        )
                        if parent and not current in parent.children:
                            parent.children.append(current)
                    else:
                        current.cumulative += weight
                        current.calls += 1
                        current.local += local
                    if (not parent) and current not in self._roots:
                        log.debug("Found new root: %s", path)
                        self._roots.append(current)
                    parent = current
            self._parent_map = path_map
        return self._roots

    def _parent(self, path):
        """Get the parent of the given path (None if it doesn't exist)"""
        return self._parent_map.get(path[:-1])

    _root = None

    @property
    def root(self):
        """Get a single root as a parent of all sampled roots"""
        if self._root is None:
            roots = self.roots
            frame = StackFrame(
                path=(),
                profile=self,
                frame=Frame(
                    name=self.name,
                    file=self.file.filename,
                    line=-1,
                    index=len(self.frames),
                    col=-1,
                    path=self.file.filename,
                    profile=self,
                ),
                cumulative=self.total,
                local=0.0,
                calls=sum([root.calls for root in roots], 0),
                children=roots,
            )
            self.parent_map[frame.path] = frame
            self._root = frame
        return self._root


class EventedProfile(Profile):
    type = "evented"
    events = None
    # TODO: implement evented mode?


class SpeedScopeFile(object):
    """Wraps a py-spy/speedscope sampling profile into RSR"""

    filename = None
    content = None
    profiles = None

    def __init__(self, content=None, filename=None):
        self.profiles = []
        if filename is not None:
            self.filename = filename
        if content is not None:
            self.read(content)
        elif filename is not None:
            try:
                with open(filename) as fh:
                    self.read(fh.read())
            except Exception as err:
                err.args = err.args + (filename,)
                raise

    def read(self, content, profile=None):
        import json

        try:
            content = json.loads(content)
        except Exception as err:
            raise ValueError("Unable to parse content: %s" % (err,))
        self.content = content
        shared_frames = [
            Frame(profile=self, index=index, **f)
            for index, f in enumerate(content["shared"]["frames"])
        ]
        for index, struct in enumerate(content["profiles"]):
            cls = (
                SampledProfile if struct["type"] == SSP_TYPE_SAMPLED else EventedProfile
            )
            profile = cls(file=self, frames=shared_frames, **struct)
            self.profiles.append(profile)
