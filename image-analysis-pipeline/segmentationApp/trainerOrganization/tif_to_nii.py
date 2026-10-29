import argparse
import os
import numpy as np
import nibabel as nib
import tifffile


def convert_tif_to_nii(input_dir: str) -> None:
    tif_files = [f for f in os.listdir(input_dir) if f.endswith('.tif')]

    if not tif_files:
        print(f"No .tif files found in {input_dir}")
        return

    for filename in tif_files:
        tif_path = os.path.join(input_dir, filename)
        img = tifffile.imread(tif_path)

        nii_img = nib.Nifti1Image(img.T, affine=np.eye(4))
        name,ext = os.path.splitext(os.path.join(input_dir,filename))
        out_path = f"{name}_img{ext}"
        out_path = out_path.replace(".tif",".nii.gz")
        nib.save(nii_img, out_path)
        print(f"Saved: {out_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert .tif images to .nii.gz for ITK-SNAP')
    parser.add_argument('input_dir', help='Directory containing .tif files')
    args = parser.parse_args()

    convert_tif_to_nii(args.input_dir)
