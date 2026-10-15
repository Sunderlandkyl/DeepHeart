"""
ExportHeartDataSequenceTest.py

Tests of ExportHeartDataLib on a SlicerHeart valve in the sequence format: a valve has one proxy node
for all of its time points, so the export has to find the time point of every requested phase and
show it while exporting. Runs on a small synthetic volume sequence (no downloads, no server); the
shared SlicerHeart test fixtures (HeartValveTestLib) are needed.
"""

import os
import sys
import unittest

import numpy as np
import vtk
import slicer
from slicer.ScriptedLoadableModule import *


def _addHeartValveTestLibToPath():
  """Make SlicerHeart's shared test fixtures (ValveAnnulusAnalysis/Testing/Python/HeartValveTestLib)
  importable: from SLICERHEART_TESTLIB_DIR, next to the loaded HeartValveLib (source checkouts), or
  from a SlicerHeart checkout next to this repository."""
  import HeartValveLib
  libDir = os.path.dirname(os.path.abspath(HeartValveLib.__file__))
  candidates = [os.environ.get("SLICERHEART_TESTLIB_DIR"), os.path.join(os.path.dirname(libDir), "Testing", "Python")]
  parent = os.path.dirname(os.path.abspath(__file__))
  for _ in range(6):
    parent = os.path.dirname(parent)
    candidates.append(os.path.join(parent, "SlicerHeart", "ValveAnnulusAnalysis", "Testing", "Python"))
  for candidate in candidates:
    if candidate and os.path.isdir(os.path.join(candidate, "HeartValveTestLib")):
      if candidate not in sys.path:
        sys.path.insert(0, candidate)
      return True
  return False


class ExportHeartDataSequenceTest(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ExportHeartDataSequenceTest"
    self.parent.categories = ["Testing.TestCases"]
    self.parent.dependencies = ["ExportHeartData", "ValveAnnulusAnalysis", "Sequences"]
    self.parent.contributors = ["DeepHeart contributors"]
    self.parent.helpText = "Tests of the DeepHeart export on sequence-format SlicerHeart valves."
    self.parent.acknowledgementText = ""


class ExportHeartDataSequenceTestWidget(ScriptedLoadableModuleWidget):
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)


class ExportHeartDataSequenceTestLogic(ScriptedLoadableModuleLogic):
  pass


class ExportHeartDataSequenceTestTest(ScriptedLoadableModuleTest):

  # Non-overlapping spheres, each larger than the 1000 voxels below which the export's island removal
  # drops a segment (the leaflet segmentation is resampled to about 0.3 mm)
  TRICUSPID_SEGMENTS = [
    ("Anterior", "Anterior leaflet", (1.0, 0.0, 0.0), (2.2, 0.0, 0.0)),
    ("Posterior", "Posterior leaflet", (0.0, 1.0, 0.0), (-2.2, 0.0, 0.0)),
    ("Septal", "Septal leaflet", (0.0, 0.0, 1.0), (0.0, 2.2, 0.0)),
  ]
  SEGMENT_RADIUS = 2.0
  TRICUSPID_TERMINOLOGY = {
    "Anterior": "tricuspid anterior leaflet",
    "Posterior": "tricuspid posterior leaflet",
    "Septal": "tricuspid septal leaflet",
  }

  def setUp(self):
    slicer.mrmlScene.Clear(0)
    import HeartValveLib.HeartValves as hv
    hv.ValveBrowsers.clear()
    hv.ValveModels.clear()
    if not _addHeartValveTestLibToPath():
      raise unittest.SkipTest("HeartValveTestLib (SlicerHeart/ValveAnnulusAnalysis/Testing/Python) not found")
    self._tempDirs = []

  def tearDown(self):
    import shutil
    for tempDir in self._tempDirs:
      shutil.rmtree(tempDir, ignore_errors=True)

  def runTest(self):
    for name in ("test_getValveModelsWithPhaseNames_time_points", "test_export_item_time_point",
                 "test_valveHasPhase", "test_export_phases_of_sequence_valve"):
      self.setUp()
      try:
        getattr(self, name)()
      finally:
        self.tearDown()

  def _tempDir(self):
    import tempfile
    tempDir = tempfile.mkdtemp(dir=slicer.app.temporaryPath)
    self._tempDirs.append(tempDir)
    return tempDir

  @staticmethod
  def _tagTerminology(segmentationNode, segmentIdToCodeMeaning):
    """Give the segments the SlicerHeart terminology the export selects leaflets by."""
    import HeartValveLib
    tlogic = slicer.modules.terminologies.logic()
    terminologyName = tlogic.LoadTerminologyFromFile(HeartValveLib.getTerminologyFile())
    category = slicer.vtkSlicerTerminologyCategory()
    termType = slicer.vtkSlicerTerminologyType()
    tags = {}
    for categoryIdx in range(tlogic.GetNumberOfCategoriesInTerminology(terminologyName)):
      tlogic.GetNthCategoryInTerminology(terminologyName, categoryIdx, category)
      for typeIdx in range(tlogic.GetNumberOfTypesInTerminologyCategory(terminologyName, category)):
        tlogic.GetNthTypeInTerminologyCategory(terminologyName, category, typeIdx, termType)
        tags[termType.GetCodeMeaning()] = tlogic.SerializeTerminologyEntry(
          terminologyName,
          category.GetCodeValue(), category.GetCodingSchemeDesignator(), category.GetCodeMeaning(),
          termType.GetCodeValue(), termType.GetCodingSchemeDesignator(), termType.GetCodeMeaning(),
          "", "", "", "", "", "", "", "", "", "")
    segmentation = segmentationNode.GetSegmentation()
    for segmentId, codeMeaning in segmentIdToCodeMeaning.items():
      segment = segmentation.GetSegment(segmentId)
      segment.SetTag(segment.GetTerminologyEntryTagName(), tags[codeMeaning])

  def _tricuspidValve(self, numFrames=6):
    """Tricuspid valve annotated at frames 1 (MS) and 3 (ED): contour, landmarks A/L/P/S and three
    leaflets with terminology. The browser is left at frame 3."""
    from HeartValveTestLib import scene
    from HeartValveTestLib.newformat import NewFormatValveFactory
    factory = NewFormatValveFactory(numFrames=numFrames)
    valveBrowser = factory.createValveBrowser("tricuspid", probePosition="TTE_APICAL")
    for frame, phase in ((1, "mid-systole"), (3, "end-diastole")):
      factory.addTimePoint(valveBrowser, frame, phase=phase)
      factory.setContour(valveBrowser, frame)
      factory.setLabels(valveBrowser, frame)
      factory.addRoi(valveBrowser)
      segmentationNode = factory.addSegmentation(valveBrowser, segments=self.TRICUSPID_SEGMENTS, withGeometry=False)
      segmentation = segmentationNode.GetSegmentation()
      for segmentId, name, color, center in self.TRICUSPID_SEGMENTS:
        segmentation.RemoveSegment(segmentId)
        scene.addSphereSegment(segmentationNode, segmentId, name, center, radius=self.SEGMENT_RADIUS, color=color)
      valveBrowser.valveModel.updateLeafletModelsFromSegmentation()
      self._tagTerminology(segmentationNode, self.TRICUSPID_TERMINOLOGY)
    return factory, valveBrowser

  # ---------------------------------------------------------------------------------------------
  # Library pieces
  # ---------------------------------------------------------------------------------------------

  def test_getValveModelsWithPhaseNames_time_points(self):
    from ExportHeartDataLib.utils import getValveModelsWithPhaseNames
    factory, valveBrowser = self._tricuspidValve()
    valveNode = valveBrowser.heartValveNode
    entries = getValveModelsWithPhaseNames(["MS", "ED", "MS+2", "ED-2"], "tricuspid")
    self.assertEqual([entry.valveModel.heartValveNode for entry in entries], [valveNode] * 4)
    self.assertEqual([entry.phase for entry in entries], ["MS", "ED", "MS", "ED"])
    self.assertEqual([entry.timePoint for entry in entries], [0, 1, 1, 0])
    with self.assertRaises(ValueError):
      getValveModelsWithPhaseNames(["MD"], "tricuspid")
    with self.assertRaises(ValueError):
      getValveModelsWithPhaseNames(["MS+1"], "tricuspid")

  def test_export_item_time_point(self):
    from ExportHeartDataLib.items import PhaseFrame
    factory, valveBrowser = self._tricuspidValve()
    valveModel = valveBrowser.valveModel
    browserNode = valveBrowser.valveBrowserNode
    self.assertEqual(browserNode.GetSelectedItemNumber(), 1)
    item = PhaseFrame(valveModel, timePoint=0)
    self.assertEqual(item.phase, "MS", "the phase is read at the item's time point")
    self.assertEqual(item.timePoint, 0)
    self.assertEqual(browserNode.GetSelectedItemNumber(), 1, "constructing the item leaves the time point as it was")
    with item.timePointShown():
      self.assertEqual(browserNode.GetSelectedItemNumber(), 0)
      self.assertEqual(PhaseFrame.getAssociatedFrameNumber(valveModel), 1)
    self.assertEqual(browserNode.GetSelectedItemNumber(), 1)
    self.assertEqual(PhaseFrame(valveModel).timePoint, 1, "defaults to the shown time point")
    self.assertEqual(PhaseFrame(valveModel).phase, "ED")

  def test_valveHasPhase(self):
    from ExportHeartDataLib.utils import valveHasPhase
    factory, valveBrowser = self._tricuspidValve()
    valveModel = valveBrowser.valveModel
    self.assertTrue(valveHasPhase(valveModel, "MS"))
    self.assertTrue(valveHasPhase(valveModel, "ED"))
    self.assertFalse(valveHasPhase(valveModel, "MD"))

  # ---------------------------------------------------------------------------------------------
  # Exporter
  # ---------------------------------------------------------------------------------------------

  def test_export_phases_of_sequence_valve(self):
    from ExportHeartDataLib.export import Exporter
    factory, valveBrowser = self._tricuspidValve()
    outputDir = self._tempDir()
    exporter = Exporter(valve_type="tricuspid",
                        reference_phase="MS",
                        cardiac_phase_frames=["MS", "ED"],
                        input_data=slicer.mrmlScene,
                        output_directory=outputDir,
                        voxel_spacing=0.5,
                        volume_dimensions=[24, 24, 24],
                        export_segmentation=True,
                        export_landmarks=True,
                        landmark_labels=["A", "P"])
    summary = exporter.export()

    def exported(kind):
      files = summary.get(kind, [])
      for path in files:
        self.assertTrue(os.path.exists(path), path)
      return sorted(os.path.basename(path) for path in files)

    # frame numbers in the file names are the (0-based) volume frames of the phases
    self.assertEqual(exported("mid-systolic-images"), ["temp_f1.nii.gz"])
    self.assertEqual(exported("end-diastolic-images"), ["temp_f3.nii.gz"])
    self.assertEqual(exported("landmarks"), ["temp_f1.fcsv", "temp_f3.fcsv"])
    self.assertEqual(exported("mid-systolic-segmentation"), ["temp_f1.nii.gz"])
    self.assertEqual(exported("end-diastolic-segmentation"), ["temp_f3.nii.gz"])
    for label in ("A", "P"):
      self.assertEqual(exported(f"mid-systolic-{label}"), ["temp_f1.nii.gz"])
      self.assertEqual(exported(f"end-diastolic-{label}"), ["temp_f3.nii.gz"])

    # the two phases were exported from their own time points: different landmarks and images
    def readLandmarks(path):
      node = slicer.util.loadMarkups(path)
      points = slicer.util.arrayFromMarkupsControlPoints(node)
      slicer.mrmlScene.RemoveNode(node)
      return points
    landmarkFiles = sorted(summary["landmarks"])
    msLandmarks = readLandmarks(landmarkFiles[0])
    edLandmarks = readLandmarks(landmarkFiles[1])
    self.assertEqual(msLandmarks.shape, edLandmarks.shape)
    self.assertGreater(float(np.abs(msLandmarks - edLandmarks).max()), 1e-3)
    msImage = slicer.util.arrayFromVolume(slicer.util.loadVolume(summary["mid-systolic-images"][0]))
    edImage = slicer.util.arrayFromVolume(slicer.util.loadVolume(summary["end-diastolic-images"][0]))
    self.assertEqual(msImage.shape, (24, 24, 24))
    self.assertNotEqual(float(msImage.mean()), float(edImage.mean()), "frames 1 and 3 have different voxel values")
    msSegmentation = slicer.util.arrayFromVolume(slicer.util.loadLabelVolume(summary["mid-systolic-segmentation"][0]))
    self.assertEqual(sorted(np.unique(msSegmentation).tolist()), [0, 1, 2, 3], "three leaflets exported")
