# -*- coding: utf-8 -*-

import os
import logging
import matplotlib.pyplot as plt
import json
import pdb
import cPickle
import json
from collections import OrderedDict
import argparse


# pyCGM2 settings
import pyCGM2
pyCGM2.CONFIG.setLoggingLevel(logging.INFO)


# pyCGM2 libraries
from pyCGM2.Tools import btkTools
import pyCGM2.enums as pyCGM2Enums
from pyCGM2.Model.CGM2 import  cgm,modelFilters, forceplates,bodySegmentParameters
#

from pyCGM2.Utils import fileManagement



if __name__ == "__main__":
    
    DEBUG = False
    parser = argparse.ArgumentParser(description='CGM1 Fitting')
    parser.add_argument('--infoFile', type=str, help='infoFile')
    parser.add_argument('--proj', type=str, help='Moment Projection. Choice : Distal, Proximal, Global')
    parser.add_argument('-mfpa',type=str,  help='manual assignment of force plates')
    parser.add_argument('-md','--markerDiameter', type=float, help='marker diameter')
    parser.add_argument('-ps','--pointSuffix', type=str, help='suffix of model outputs')
    parser.add_argument('--check', action='store_true', help='force model output suffix')
    parser.add_argument('-fs','--fileSuffix', type=str, help='suffix of output file')
    args = parser.parse_args()




    # --------------------GOBAL SETTINGS ------------------------------

    # global setting ( in user/AppData)
    inputs = json.loads(open(str(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH+"CGM1-pyCGM2.settings")).read(),object_pairs_hook=OrderedDict)

    # --------------------SESSION SETTINGS ------------------------------
    if DEBUG:
        DATA_PATH = "C:\\Users\\HLS501\\Documents\\VICON DATA\\pyCGM2-Data\\Datasets Tests\\Florent Moissenet\\sample\\"
        infoSettings = json.loads(open(DATA_PATH + 'pyCGM2.info').read(),object_pairs_hook=OrderedDict)

    else:
        DATA_PATH =os.getcwd()+"\\"
        infoSettingsFilename = "pyCGM2.info" if args.infoFile is None else  args.infoFile
            
        infoSettings = json.loads(open(infoSettingsFilename).read(),object_pairs_hook=OrderedDict)


    # --------------------CONFIGURATION ------------------------------
    if args.markerDiameter is not None:
        markerDiameter = float(args.markerDiameter)
        logging.warning("marker diameter forced : %s", str(float(args.markerDiameter)))
    else:
        markerDiameter = float(inputs["Global"]["Marker diameter"])

    if args.check:
        pointSuffix="cgm1.0"
    else:
        if args.pointSuffix is not None:
            pointSuffix = args.pointSuffix
        else:
            if args.pointSuffix is not None:
                pointSuffix = args.pointSuffix
            else:
                pointSuffix = inputs["Global"]["Point suffix"]

    if args.proj is not None:
        if args.proj == "Distal":
            momentProjection = pyCGM2Enums.MomentProjection.Distal
        elif args.proj == "Proximal":
            momentProjection = pyCGM2Enums.MomentProjection.Proximal
        elif args.proj == "Global":
            momentProjection = pyCGM2Enums.MomentProjection.Global
        elif args.proj == "JCS":
            momentProjection = pyCGM2Enums.MomentProjection.JCS
        else:
            raise Exception("[pyCGM2] Moment projection doesn t recognise in your inputs. choice is Proximal, Distal or Global")

    else:
        if inputs["Fitting"]["Moment Projection"] == "Distal":
            momentProjection = pyCGM2Enums.MomentProjection.Distal
        elif inputs["Fitting"]["Moment Projection"] == "Proximal":
            momentProjection = pyCGM2Enums.MomentProjection.Proximal
        elif inputs["Fitting"]["Moment Projection"] == "Global":
            momentProjection = pyCGM2Enums.MomentProjection.Global
        elif inputs["Fitting"]["Moment Projection"] == "JCS":
            momentProjection = pyCGM2Enums.MomentProjection.JCS
        else:
            raise Exception("[pyCGM2] Moment projection doesn t recognise in your inputs. choice is Proximal, Distal or Global")



    # --------------------------TRANSLATORS ------------------------------------
    #  translators management
    translators = fileManagement.manage_pycgm2Translators(DATA_PATH,"CGM1.translators")
    if not translators:
       translators = inputs["Translators"]
       

    # ------------------ pyCGM2 MODEL -----------------------------------

    if not os.path.isfile(DATA_PATH +  "pyCGM2.model"):
        raise Exception ("pyCGM2.model file doesn't exist. Run Calibration operation")
    else:
        f = open(DATA_PATH + 'pyCGM2.model', 'r')
        model = cPickle.load(f)
        f.close()

    # --------------------------CHECKING -----------------------------------    
    # check model is the CGM1
    logging.info("loaded model : %s" %(model.version ))
    if model.version != "CGM1.0":
        raise Exception ("pyCGM2.model file was not calibrated from the CGM1.0 calibration pipeline"%model.version)

    # --------------------------MODELLLING--------------------------
    motionTrials = infoSettings["Modelling"]["Trials"]["Motion"]


    for trial in motionTrials:

        acqGait = btkTools.smartReader(str(DATA_PATH + trial))

        btkTools.checkMultipleSubject(acqGait)
        acqGait =  btkTools.applyTranslators(acqGait,translators)
        validFrames,vff,vlf = btkTools.findValidFrames(acqGait,cgm.CGM1LowerLimbs.MARKERS)

        scp=modelFilters.StaticCalibrationProcedure(model) # procedure

        # ---Motion filter----
        modMotion=modelFilters.ModelMotionFilter(scp,acqGait,model,pyCGM2Enums.motionMethod.Determinist,
                                                  markerDiameter=markerDiameter,
                                                  viconCGM1compatible=True)

        modMotion.compute()


        #---- Joint kinematics----
        # relative angles
        modelFilters.ModelJCSFilter(model,acqGait).compute(description="vectoriel", pointLabelSuffix=pointSuffix)

        # detection of traveling axis
        longitudinalAxis,forwardProgression,globalFrame = btkTools.findProgressionAxisFromPelvicMarkers(acqGait,["LASI","RASI","RPSI","LPSI"])

        # absolute angles
        modelFilters.ModelAbsoluteAnglesFilter(model,acqGait,
                                               segmentLabels=["Left Foot","Right Foot","Pelvis"],
                                                angleLabels=["LFootProgress", "RFootProgress","Pelvis"],
                                                eulerSequences=["TOR","TOR", "TOR"],
                                                globalFrameOrientation = globalFrame,
                                                forwardProgression = forwardProgression).compute(pointLabelSuffix=pointSuffix)

        #---- Body segment parameters----
        bspModel = bodySegmentParameters.Bsp(model)
        bspModel.compute()

        # --- force plate handling----
        # find foot  in contact
        mappedForcePlate = forceplates.matchingFootSideOnForceplate(acqGait)
        forceplates.addForcePlateGeneralEvents(acqGait,mappedForcePlate)
        logging.info("Force plate assignment : %s" %mappedForcePlate)

        if args.mfpa is not None:
            if len(args.mfpa) != len(mappedForcePlate):
                raise Exception("[pyCGM2] manual force plate assignment badly sets. Wrong force plate number. %s force plate require" %(str(len(mappedForcePlate))))
            else:
                mappedForcePlate = args.mfpa
                logging.warning("Force plates assign manually")
                forceplates.addForcePlateGeneralEvents(acqGait,mappedForcePlate)


        # assembly foot and force plate
        modelFilters.ForcePlateAssemblyFilter(model,acqGait,mappedForcePlate,
                                 leftSegmentLabel="Left Foot",
                                 rightSegmentLabel="Right Foot").compute()

        #---- Joint kinetics----
        idp = modelFilters.CGMLowerlimbInverseDynamicProcedure()
        modelFilters.InverseDynamicFilter(model,
                             acqGait,
                             procedure = idp,
                             projection = momentProjection,
                             viconCGM1compatible=True
                             ).compute(pointLabelSuffix=pointSuffix)

        #---- Joint energetics----
        modelFilters.JointPowerFilter(model,acqGait).compute(pointLabelSuffix=pointSuffix)

        # ----------------------SAVE-------------------------------------------
        # new static file
        if args.fileSuffix is not None:
            btkTools.smartWriter(acqGait, str(DATA_PATH+trial[:-4]+"-modelled.c3d"))
        else:
            btkTools.smartWriter(acqGait, str(DATA_PATH+trial[:-4]+"-modelled-"+args.fileSuffix+".c3d"))
            