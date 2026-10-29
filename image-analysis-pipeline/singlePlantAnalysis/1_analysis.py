""" 
ChronoRoot: High-throughput phenotyping by deep learning reveals novel temporal parameters of plant root system architecture
Copyright (C) 2020 Nicolás Gaggion

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from analysis.plantAnalysis import plantAnalysis
from analysis.qr import aruco_detect, aruco_get_pixel_size
from analysis.utils.fileUtilities import getImages
import argparse
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ChronoRoot: High-throughput phenotyping by deep learning reveals novel temporal parameters of plant root system architecture')
    parser.add_argument('--config', type=str, help='Path to the configuration file (default: config.json)')
    parser.add_argument('--rerun', action='store_true', default=False, help='Reruns the analysis, even if the results already exist')
    parser.add_argument('--restart', action='store_true', default=False, help='Reruns the analysis from scratch, ignoring any previous bounding box or root start point')
    
    args = parser.parse_args()
        
    conf = json.load(open(args.config))
    
    if args.restart:
        del conf['bounding box']
        del conf['seed']
    
    try:
        conf['fileKey'] = conf["Experiment"]
    except:
        conf['fileKey'] = conf["identifierField"]
        conf['Experiment'] = conf["identifierField"]
        
    conf['sequenceLabel'] = conf['Experiment'] + "_" + conf['Images'] + "_" + str(conf['plant'])
    conf['Plant'] = 'Arabidopsis thaliana'
    
    if not conf.get('videoHasQRbutton', True) and not conf.get('videoHasArucoButton', True):
        pixel_size = float(conf['knownDistance']) / float(conf['pixelDistance'])
        conf['pixel_size'] = pixel_size

    # --- ArUco debug: print the detected marker pixel width ---
    if conf.get('videoHasArucoButton', False) or conf.get('videoHasAruco', False):
        print("[ArUco Debug] ArUco checkbox is selected — scanning for markers...")
        try:
            image_paths, _ = getImages(conf)
            found = False
            for img_path in image_paths[:20]:
                aruco_result = aruco_detect(img_path)
                if aruco_result is not None:
                    pixel_width = aruco_get_pixel_size(aruco_result[0])
                    print(f"[ArUco Debug] Marker found in: {img_path}")
                    print(f"[ArUco Debug] Marker width (pixel distance): {pixel_width:.2f} px")
                    found = True
                    break
            if not found:
                print("[ArUco Debug] No ArUco marker detected in the first 20 images.")
        except Exception as e:
            print(f"[ArUco Debug] Error during detection: {e}")
        
    if 'bounding box' in conf and args.rerun:
        plantAnalysis(conf, True)
    else:
        plantAnalysis(conf, False)