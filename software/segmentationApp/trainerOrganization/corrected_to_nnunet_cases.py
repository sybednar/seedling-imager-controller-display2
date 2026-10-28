import argparse
import os
import json
import shutil
import nibabel as nib
import cv2
import numpy as np
import tifffile


def convert_tifs_to_png(input_dir: str) -> None:
    tif_files = [
        f for f in os.listdir(input_dir)
        if f.lower().endswith(('.tif', '.tiff'))
    ]

    for tif_file in tif_files:
        stem = os.path.splitext(tif_file)[0]
        png_path = os.path.join(input_dir, f'{stem}.png')

        if os.path.exists(png_path):
            continue

        image = tifffile.imread(os.path.join(input_dir, tif_file))
        cv2.imwrite(png_path, image)
        print(f"Converted {tif_file} -> {stem}.png")


def convert(input_dir: str, images_out: str, labels_out: str, start_case: int) -> None:
    os.makedirs(images_out, exist_ok=True)
    os.makedirs(labels_out, exist_ok=True)

    convert_tifs_to_png(input_dir)

    mask_files = sorted(
        f for f in os.listdir(input_dir)
        if f.endswith('.nii.gz') and not f.endswith('_img.nii.gz')
    )

    mapping = {}
    case_id = start_case

    for mask_file in mask_files:
        stem = mask_file[:-len('.nii.gz')]
        png_path = os.path.join(input_dir, f'{stem}.png')

        if not os.path.exists(png_path):
            print(f"Skipping {stem}: no matching .png found")
            continue

        mask = nib.load(os.path.join(input_dir, mask_file)).get_fdata().T
        if mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]

        image = cv2.imread(png_path, 0)

        if image.shape != mask.shape:
            print(f"Skipping {stem}: shape mismatch image={image.shape} mask={mask.shape}")
            continue

        case_name = f'image_{case_id}'
        shutil.copy(png_path, os.path.join(images_out, f'{case_name}_0000.png'))
        cv2.imwrite(os.path.join(labels_out, f'{case_name}.png'), mask.astype('uint8'))

        mapping[case_name] = stem
        print(f"{stem} -> {case_name}")
        case_id += 1

    mapping_path = os.path.join(labels_out, '..', 'case_mapping.json')
    with open(mapping_path, 'w') as f:
        json.dump(mapping, f, indent=4)

    print(f"\nConverted {len(mapping)} cases ({start_case} to {case_id - 1}).")
    print(f"Mapping saved to {os.path.abspath(mapping_path)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Convert corrected .nii.gz masks + matching .png images into nnUNet image_N naming'
    )
    parser.add_argument('input_dir', help='Directory with corrected <name>.nii.gz masks and <name>.png images')
    parser.add_argument('images_out', help='Output directory for image_N_0000.png images (imagesTr)')
    parser.add_argument('labels_out', help='Output directory for image_N.png masks (labelsTr)')
    parser.add_argument('--start-case', type=int, default=797, help='First case number to use (default 797)')
    args = parser.parse_args()

    convert(args.input_dir, args.images_out, args.labels_out, args.start_case)
