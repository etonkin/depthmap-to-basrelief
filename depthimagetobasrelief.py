#original code source 
#https://dev.realsenseai.com/docs/depth-image-compression-by-colorization-for-intel-realsense-depth-cameras
import argparse
import numpy as np
import pandas as pd
from extrude import extrude_depth_3d
import cv2
import math
import os
from PIL import Image
import tempfile;
from distutils.dir_util import copy_tree

default_seed = 2024
default_batch_size = 4
default_bas_plane_near = 0.0
default_bas_plane_far = 1.0
default_bas_embossing = 20
default_bas_size_longest_px = 512
default_bas_size_longest_cm = 10
default_bas_filter_size = 3
default_bas_frame_thickness = 3
default_bas_frame_near = 1
default_bas_frame_far = 1

## from ETH Zurich's huggingface depth-to-3d-print
def process_bas(
    input_image,
    path_input_depth,
    basOutputPath,
    path_input_rgb=None,
    plane_near=default_bas_plane_near,
    plane_far=default_bas_plane_far,
    embossing=default_bas_embossing,
    size_longest_px=default_bas_size_longest_px,
    size_longest_cm=default_bas_size_longest_cm,
    filter_size=default_bas_filter_size,
    frame_thickness=default_bas_frame_thickness,
    frame_near=default_bas_frame_near,
    frame_far=default_bas_frame_far,
):
    input_depth = Image.open(path_input_depth)
    print(input_depth);
    depth_longest_px = max(input_depth.size)
    input_rgb=None;

    if plane_near >= plane_far:
        raise gr.Error("NEAR plane must have a value smaller than the FAR plane")

    name_base, name_ext = os.path.splitext(os.path.basename(path_input_depth))
    print(f"Processing bas-relief {name_base}{name_ext}")

    path_output_dir = tempfile.mkdtemp()

    def _process_3d(
        size_longest_px,
        filter_size,
        vertex_colors,
        scene_lights,
        output_model_scale=None,
        prepare_for_3d_printing=False,
        zip_outputs=False,
    ):
        image_new_w = size_longest_px * input_depth.width // depth_longest_px
        image_new_h = size_longest_px * input_depth.height // depth_longest_px
        image_new_sz = (image_new_w, image_new_h)

        path_depth_new = os.path.join(
            path_output_dir, f"{name_base}_depth_{size_longest_px}.png"
        )
        (
            input_depth.convert(mode="F")
            .resize(image_new_sz, Image.BILINEAR)
            .convert("I")
            .save(path_depth_new)
        )
        path_rgb_new = None
        if input_rgb is not None:
            path_rgb_new = os.path.join(
                path_output_dir, f"{name_base}_rgb_{size_longest_px}{name_ext}"
            )
            input_rgb.resize(image_new_sz, Image.LANCZOS).save(path_rgb_new)

        path_glb, path_stl, path_obj = extrude_depth_3d(
            path_depth_new,
            path_rgb_new,
            output_model_scale=(
                size_longest_cm * 10
                if output_model_scale is None
                else output_model_scale
            ),
            filter_size=filter_size,
            coef_near=plane_near,
            coef_far=plane_far,
            emboss=embossing / 100,
            f_thic=frame_thickness / 100,
            f_near=frame_near / 100,
            f_back=frame_far / 100,
            vertex_colors=vertex_colors,
            scene_lights=scene_lights,
            prepare_for_3d_printing=prepare_for_3d_printing,
            zip_outputs=zip_outputs,
            smoothing=False,
            smoothingmethod="",
        )
        
        return path_glb, path_stl, path_obj

    path_viewer_glb, _, _ = _process_3d(
        256, filter_size, vertex_colors=False, scene_lights=True, output_model_scale=1
    )
    path_files_glb, path_files_stl, path_files_obj = _process_3d(
        size_longest_px,
        filter_size,
        vertex_colors=True,
        scene_lights=False,
        prepare_for_3d_printing=True,
        zip_outputs=True,
    )
    copy_tree(path_output_dir,basOutputPath)
    return path_viewer_glb, [path_files_glb, path_files_stl, path_files_obj]




_width = 848
_height = 480
is_disparity = False
min_depth = 0.29  # to avoid depth inversion, it’s offset from 0.3 to 0.29. Please see Figure 7
max_depth = 10.0
min_disparity = 1.0 / max_depth
max_disparity = 1.0 / min_depth

def RGBtoD(r, g, b):
    global max_depth;
    global min_depth;
    global min_disparity;
    global max_disparity;
    # conversion from RGB color to quantized depth value
    dNormal=0;
        # the hue bar goes: solid red 255, increasing green (first 1/6)
        # solid green at 255, decreasing red
        # zero red, solid green at 255, increasing blue
        # zero red, solid blue at 255, decreasing green
        # solid blue at 255, increasing red 
        # solid red at 255, decreasing blue
        # r is greater than g and b at extreme right and extreme left

    if (b + g + r) < 255: ## honestly I'm not sure what to do about this: transitioning back from jpeg or whatever webby stuff, you do lose colour hues apparently and so a lot of detail is lost if you enforce this rule. Needs thought. 
        # for a colour to be in this hue list it always has to equal 255. Otherwise, you should return zero or NULL or something
        return 0
    elif r >= g and r >= b:
        # this is the extreme left of the hue colour bar: red + green no blue
        if g >= b:
            dNormal=g - b
        #this is the extreme right of the hue colour bar: diminishing blue, red is always 255
        #else:
        #    dNormal=(g - b) + 1529
    elif (g >=r and g >= b):
        dNormal=b-r + 510;
    elif ( b>=g and b >= r):
        dNormal= r - g + 1020;
   # drecovery= min_depth+((max_depth-min_depth)*dNormal)/1529;
    
    drecovery=1529/(1529*min_disparity+(max_disparity-min_disparity)*dNormal)
    return drecovery;

def convert_depth(input_color_data_array, depth_units, output_depth_data_array):
    in_idx = 0
    out_idx = 0
    in_data = input_color_data_array
    out_data = output_depth_data_array

    for i in range(_height):
        for j in range(_width):
            R = in_data[in_idx]
            G = in_data[in_idx + 1]
            B = in_data[in_idx + 2]
            in_idx += 3

            out_value = RGBtoD(R, G, B)

            if out_value > 0:
                if not is_disparity:
                    z_value = int(min_depth + (max_depth - min_depth) * out_value / 1529.0 + 0.5)
                    out_data[out_idx] = z_value
                else:
                    disp_value = min_disparity + (max_disparity - min_disparity) * out_value / 1529.0
                    out_data[out_idx] = int((1.0 / disp_value) / depth_units + 0.5)
            else:
                out_data[out_idx] = 0
            out_idx += 1

def convert_single_pixel(input_colour_pixel):
    R=input_colour_pixel[0];
    G=input_colour_pixel[1];
    B=input_colour_pixel[2];
    out_value=RGBtoD(R,G,B)
    return out_value;

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--depthPath', dest='depthPath',
                        help='depth map path',
                        default='depth.png', type=str)

    parser.add_argument('--output', dest='outputPath',
                        help='output path',
                        default='output.png', type=str)
    parser.add_argument('--output-inverted', dest='outputInvertedPath',
                        help='inverted-greyscale output image path',
                        default='output-inverted.png', type=str)
    parser.add_argument('--make_bas_relief',dest="makeBasRelief", 
                        help="create a bas-relief in ETH-Zurich style",
                        action="store_true")
    parser.add_argument('--output-basrelief',dest='basOutputPath',
                        help='make ETH Zurich style bas relief output path',
                        default='basrelief-output',type=str);

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    print("STARTED");
    args = parse_args()
    # open image file and have a look at it
    img = cv2.imread(args.depthPath, -1).astype(np.int16) #/1000.0
    img_h=img.shape[0];
    img_w=img.shape[1];
    trial_arr=np.zeros((img_h,img_w))
    # create blank grayscale image for output 
    gray_value=0
    output_image=np.full((img_h,img_w), gray_value, dtype=np.uint16);
    for i in range(0,img_h):
        for j in range (0,img_w):
            outpixel=convert_single_pixel(img[i][j]);
            #output_image[i][j]=outpixel;
            trial_arr[i][j]=outpixel;
    imax=trial_arr.max();
    # arbitrarily set to a value that looks pleasant to me in 3d rendering 
    trial_arr *=255*60/imax;
    for i in range (0,img_h):
        for j in range (0,img_w):
            output_image[i][j]=trial_arr[i][j];
    #cv2.imwrite("output.png",output_image)
    cv2.imwrite(args.outputPath,output_image)
    inverted_image=cv2.bitwise_not(output_image);
    cv2.imwrite(args.outputInvertedPath,inverted_image);
    df=pd.DataFrame(trial_arr)
    #df.to_csv('outputarr.txt');
    process_bas(inverted_image,args.outputInvertedPath,args.basOutputPath);
