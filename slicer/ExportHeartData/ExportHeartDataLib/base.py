from abc import ABC, abstractmethod
import contextlib
import logging
import slicer
from ExportHeartDataLib.constants import APPLICATION_NAME
from ExportHeartDataLib.summary import ExportSummary
from ExportHeartDataLib.exceptions import NoAssociatedFrameNumberFound


class ExportBuilder(object):

  def __init__(self):
    self._items = []

  def add_export_item(self, item) -> None:
    assert isinstance(item, ExportItem)
    self._items.append(item)

  def export(self):
    for item in self._items:
      with item.timePointShown():
        item()

  def requirementsSatisfied(self):
    satisfied = []
    messages = []
    for item in self._items:
      with item.timePointShown():
        valid, message = item.verify()
      satisfied.append(valid)
      if message:
        messages.append(message)
    return all(satisfied), messages


class ExportItem(ABC):

  exportSummarizer = None
  prefix = None
  outputDir = None
  referenceVolumeNode = None
  probeToRasTransform = None

  @classmethod
  def getAssociatedFrameNumber(cls, valveModel):
    frameNumber = valveModel.getValveVolumeSequenceIndex()
    if frameNumber == -1:
      raise NoAssociatedFrameNumberFound(f"No associated frame number found for {valveModel.getCardiacCyclePhase()}")
    return frameNumber

  @staticmethod
  def currentTimePoint(valveModel):
    """Time point (valve browser item number) the valve shows now; -1 for a valve that is not in the
    sequence format."""
    from HeartValveLib.helpers import getValveBrowserNode
    browserNode = getValveBrowserNode(valveModel.heartValveNode)
    return browserNode.GetSelectedItemNumber() if browserNode else -1

  @classmethod
  def cleanup(cls):
    if cls.probeToRasTransform is not None:
      slicer.mrmlScene.RemoveNode(cls.probeToRasTransform)
      cls.probeToRasTransform = None
    if cls.referenceVolumeNode is not None:
      slicer.mrmlScene.RemoveNode(cls.referenceVolumeNode)
      cls.referenceVolumeNode = None

  @classmethod
  def requiredAttributesSet(cls):
    return cls.outputDir is not None and \
           cls.referenceVolumeNode is not None and \
           cls.probeToRasTransform is not None and \
           cls.prefix is not None

  @property
  def phase(self):
    return self._phase

  @property
  def timePoint(self):
    return self._timePoint

  @contextlib.contextmanager
  def timePointShown(self):
    """Show the time point this item exports for the duration of the block (in the sequence format a
    valve has one proxy node for all of its time points); the time point shown before is restored after.
    """
    from HeartValveLib.helpers import valveTimePointSelected
    with valveTimePointSelected(self._valveModel.heartValveNode, self._timePoint):
      yield

  @staticmethod
  def getLogger():
    return logging.getLogger(APPLICATION_NAME)

  @classmethod
  def setExportSummarizer(cls, summarizer):
    assert isinstance(summarizer, ExportSummary)
    cls.exportSummarizer = summarizer

  @classmethod
  def saveNode(cls, node, outputFile, kind=None):
    node.SetAndObserveTransformNodeID(cls.probeToRasTransform.GetID())
    slicer.modules.transforms.logic().hardenTransform(node)
    if cls.exportSummarizer:
      assert kind is not None
      cls.exportSummarizer.add_export_item(kind, outputFile)
    return slicer.util.saveNode(node, str(outputFile))

  def __init__(self, valveModel, phase=None, suffix="", timePoint=None):
    """
    :param timePoint: time point (valve browser item number) of the valve this item exports; the time
      point the valve shows now when not given
    """
    assert valveModel is not None
    self._valveModel = valveModel
    self._suffix = suffix
    self._timePoint = timePoint if timePoint is not None else self.currentTimePoint(valveModel)
    if phase:
      self._phase = phase
    else:
      from HeartValveLib.helpers import getValvePhaseShortName
      with self.timePointShown():
        self._phase = getValvePhaseShortName(valveModel)

  @abstractmethod
  def __call__(self):
    # before calling this, needs to check if necessary attributes were set
    pass

  @abstractmethod
  def verify(self):
    pass
