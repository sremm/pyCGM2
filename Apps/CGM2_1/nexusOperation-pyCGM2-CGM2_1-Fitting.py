# -*- coding: utf-8 -*-

import os
import logging
import matplotlib.pyplot as plt
import json
import pdb
import cPickle
from shutil import copyfile
import json
from collections import OrderedDict
import argparse

# pyCGM2 settings
import pyCGM2
pyCGM2.CONFIG.setLoggingLevel(logging.INFO)

# vicon nexus
import ViconNexus



# pyCGM2 libraries
from pyCGM2.Tools import btkTools,nexusTools
import pyCGM2.enums as pyCGM2Enums
from pyCGM2.Model.CGM2 import cgm, modelFilters, forceplates,bodySegmentParameters
#
from pyCGM2 import viconInterface
from pyCGM2.Utils import fileManagement



if __name__ == "__main__":


    DEBUG = False

    NEXUS = ViconNexus.ViconNexus()
    NEXUS_PYTHON_CONNECTED = NEXUS.Client.IsConnected()

    parser = argparse.ArgumentParser(description='CGM2-1 Fitting')
    parser.add_argument('--proj', type=str, help='Moment Projection. Choice : Distal, Proximal, Global')
    parser.add_argument('-mfpa',type=str,  help='manual assignment of force plates')
    parser.add_argument('-md','--markerDiameter', type=float, help='marker diameter')
    parser.add_argument('--check', action='store_true', help='force model output suffix')
    args = parser.parse_args()


    if NEXUS_PYTHON_CONNECTED: # run Operation

        # --------------------------GLOBAL SETTINGS ------------------------------------
        # global setting ( in user/AppData)
        inputs = json.loads(open(str(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH+"CGM2_1-pyCGM2.settings")).read(),object_pairs_hook=OrderedDict)

        # --------------------------LOADING ------------------------------------
        # --- acquisition file and path----
        if DEBUG:
            DATA_PATH = "C:\\Users\\AAA34169\\Documents\\VICON DATA\\pyCGM2-Data\\CGM1\\CGM1-NexusPlugin\\New Session 3\\"
            reconstructFilenameLabelledNoExt = "MRI-US-01, 2008-08-08, 3DGA 12"
            NEXUS.OpenTrial( str(DATA_PATH+reconstructFilenameLabelledNoExt), 10 )

        else:
            DATA_PATH, reconstructFilenameLabelledNoExt = NEXUS.GetTrialName()

        reconstructFilenameLabelled = reconstructFilenameLabelledNoExt+".c3d"

        logging.info( "data Path: "+ DATA_PATH )
        logging.info( "calibration file: "+ reconstructFilenameLabelled)


        # --------------------------SUBJECT ------------------------------------
        subjects = NEXUS.GetSubjectNames()
        subject = nexusTools.ckeckActivatedSubject(NEXUS,subjects)
        logging.info(  "Subject name : " + subject  )

        # --------------------pyCGM2 MODEL ------------------------------
        if not os.path.isfile(DATA_PATH + subject + "-pyCGM2.model"):
            raise Exception ("%s-pyCGM2.model file doesn't exist. Run Calibration operation"%subject)
        else:
            f = open(DATA_PATH + subject + '-pyCGM2.model', 'r')
            model = cPickle.load(f)
            f.close()

        # --------------------------CHECKING -----------------------------------    
        # check model
        if repr(model) != "LowerLimb CGM2.1":
            logging.info("loaded model : %s" %(repr(model) ))
            raise Exception ("%s-pyCGM2.model file was not calibrated from the CGM2.1 calibration pipeline"%subject)

        # --------------------------SESSION INFOS ------------------------------------
        # info file
        infoSettings = fileManagement.manage_pycgm2SessionInfos(DATA_PATH,subject)

        #  translators management
        infoSettings = fileManagement.manage_pycgm2Translators(DATA_PATH,"CGM1.translators")
        if not infoSettings:
           translators = inputs["Translators"]

        # --------------------------CONFIG ------------------------------------

        if args.markerDiameter is not None: 
            markerDiameter = float(args.markerDiameter)
            logging.warning("marker diameter forced : %s", str(float(args.markerDiameter)))
        else:
            markerDiameter = float(inputs["Global"]["Marker diameter"])
            
            
        if args.check:
            pointSuffix="cgm2.1"
        else:
            pointSuffix = inputs["Global"]["Point suffix"]

        if args.proj is not None:        
            if args.proj == "Distal":
                momentProjection = pyCGM2Enums.MomentProjection.Distal
            elif args.proj == "Proximal":
                momentProjection = pyCGM2Enums.MomentProjection.Proximal
            elif args.proj == "Global":
                momentProjection = pyCGM2Enums.MomentProjection.Global
            else:
                raise Exception("[pyCGM2] Moment projection doesn t recognise in your inputs. choice is Proximal, Distal or Global")

        else:        
            if inputs["Fitting"]["Moment Projection"] == "Distal":
                momentProjection = pyCGM2Enums.MomentProjection.Distal
            elif inputs["Fitting"]["Moment Projection"] == "Proximal":
                momentProjection = pyCGM2Enums.MomentProjection.Proximal
            elif inputs["Fitting"]["Moment Projection"] == "Global":
                momentProjection = pyCGM2Enums.MomentProjection.Global
            else:
                raise Exception("[pyCGM2] Moment projection doesn t recognise in your inputs. choice is Proximal, Distal or Global")      


        # --------------------------ACQUISITION ------------------------------------

        # --- btk acquisition ----        
        acqGait = btkTools.smartReader(str(DATA_PATH + reconstructFilenameLabelled))

        btkTools.checkMultipleSubject(acqGait)
        acqGait =  btkTools.applyTranslators(acqGait,translators)
        validFrames,vff,vlf = btkTools.findValidFrames(acqGait,cgm.CGM1LowerLimbs.MARKERS)  
              
        
        scp=modelFilters.StaticCalibrationProcedure(model) 
        # ---Motion filter----    
        modMotion=modelFilters.ModelMotionFilter(scp,acqGait,model,pyCGM2Enums.motionMethod.Determinist,
                                                  markerDiameter=markerDiameter)

        modMotion.compute()


        #---- Joint kinematics----
        # relative angles
        modelFilters.ModelJCSFilter(model,acqGait).compute(description="vectoriel", pointLabelSuffix=pointSuffix)

        # detection of traveling axis
        longitudinalAxis,forwardProgression,globalFrame = btkTools.findProgressionAxisFromPelvicMarkers(acqGait,["LASI","LPSI","RASI","RPSI"]) 
        
        # absolute angles        
        modelFilters.ModelAbsoluteAnglesFilter(model,acqGait,
                                               segmentLabels=["Left Foot","Right Foot","Pelvis"],
                                                angleLabels=["LFootProgress", "RFootProgress","Pelvis"],
                                                eulerSequences=["TOR","TOR", "ROT"],
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
                forceplates.addForcePlateGeneralEvents(acqGait,mappedForcePlate)
                logging.warning("Force plates assign manually")

        # assembly foot and force plate        
        modelFilters.ForcePlateAssemblyFilter(model,acqGait,mappedForcePlate,
                                 leftSegmentLabel="Left Foot",
                                 rightSegmentLabel="Right Foot").compute()

        #---- Joint kinetics----
        idp = modelFilters.CGMLowerlimbInverseDynamicProcedure()
        modelFilters.InverseDynamicFilter(model,
                             acqGait,
                             procedure = idp,
                             projection = momentProjection
                             ).compute(pointLabelSuffix=pointSuffix)

        #---- Joint energetics----
        modelFilters.JointPowerFilter(model,acqGait).compute(pointLabelSuffix=pointSuffix)

        #---- zero unvalid frames ---
        btkTools.applyValidFramesOnOutput(acqGait,validFrames)  

        # ----------------------DISPLAY ON VICON-------------------------------
        viconInterface.ViconInterface(NEXUS,model,acqGait,subject,pointSuffix).run()
        nexusTools.createGeneralEvents(NEXUS,subject,acqGait,["Left-FP","Right-FP"])

        # ========END of the nexus OPERATION if run from Nexus  =========

        if DEBUG:

            NEXUS.SaveTrial(30)
    
            
    else:
        raise Exception("NO Nexus connection. Turn on Nexus")
