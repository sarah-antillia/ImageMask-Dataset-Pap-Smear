# Copyright 2024 antillia.com Toshiyuki Arai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# ImageMaskDatasetGenerator.py
# 2024/04/13 to-arai

import os
import sys
import glob

import shutil
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import cv2
import traceback
import numpy as np
from ConfigParser  import ConfigParser

from SeamlessClone import SeamlessClone

# 2023/07/23 Modified resize_to_square method to use SeamlessClone if mask=False 

  
class ImageMaskDatasetGenerator:
  
  def __init__(self, resize=312, cropsize=128, seamless_cloning=False):
    self.RESIZE  = resize
     
    self.resize_ratio = 1
    self.blur_mask    = True
    self.CROPSIZE    = cropsize
    self.seamless_cloning = seamless_cloning

    self.seamless_clone = SeamlessClone()
    
  def crop_image(self, image):
    w, h = image.size
    left  = (w - self.CROPSIZE)//2
    upper = (h - self.CROPSIZE)//2
    right = left  + self.CROPSIZE
    lower = upper + self.CROPSIZE

    return  image.crop( (left, upper, right, lower))

  # cropped = img.crop( (left, upper, right, lower) )
  def augment(self, image, output_dir, filename, expand):
    # 2023/07/22
    ANGLES = [30, 90, 120, 150, 180, 210, 240, 270, 300, 330]

    for angle in ANGLES:
      rotated_image = image.rotate(angle)
      output_filename = "rotated_" + str(angle) + "_" + filename
      rotated_image_file = os.path.join(output_dir, output_filename)
      cropped  =  self.crop_image(rotated_image)
      cropped  = cropped.resize((expand, expand))
      cropped.save(rotated_image_file)
      print("=== Saved {}".format(rotated_image_file))
    # Create mirrored image
    mirrored = ImageOps.mirror(image)
    output_filename = "mirrored_" + filename
    image_filepath = os.path.join(output_dir, output_filename)
    cropped = self.crop_image(mirrored)
    cropped = cropped.resize((expand, expand))
    cropped.save(image_filepath)
    print("=== Saved {}".format(image_filepath))
        
    # Create flipped image
    flipped = ImageOps.flip(image)
    output_filename = "flipped_" + filename

    image_filepath = os.path.join(output_dir, output_filename)
    cropped = self.crop_image(flipped)
    cropped = cropped.resize((expand, expand))
    cropped.save(image_filepath)
    print("=== Saved {}".format(image_filepath))

  # 2023/07/23 Modified to use SeamlessClone if mask=False
  def resize_to_square(self, image, mask=False):
     w, h  = image.size
     pixel = image.getpixel((w-2, h-2))
     background = Image.new("RGB", (self.RESIZE, self.RESIZE), pixel)
     bigger = w
     if h > bigger:
       bigger = h
     x = (self.RESIZE - w) // 2
     y = (self.RESIZE - h) // 2
     background.paste(image, (x, y))
     if mask == True:
       return background
     
     # mask==False case
     if self.seamless_cloning == False:
       return background
     else:
       mask = Image.new("L", (self.RESIZE, self.RESIZE))
       draw = ImageDraw.Draw(mask)
       draw.rectangle((x, y, x + w, y + h), fill="white")
       target = Image.new("RGB", (self.RESIZE, self.RESIZE), pixel)

       cloned = self.seamless_clone.seamlessClone(background, target, mask)
       return cloned
     

  def create(self, categorized_input_dir, mask_color,  
                            categorized_images_dir, categorized_masks_dir, expand, debug=False):

    if os.path.exists(categorized_images_dir):
      shutil.rmtree(categorized_images_dir)
    if not os.path.exists(categorized_images_dir):
      os.makedirs(categorized_images_dir)

    if os.path.exists(categorized_masks_dir):
      shutil.rmtree(categorized_masks_dir)
    if not os.path.exists(categorized_masks_dir):
      os.makedirs(categorized_masks_dir)

    xpattern = categorized_input_dir + "/*-d.bmp"
    mask_files = glob.glob(xpattern)
    if mask_files == None or len(mask_files) == 0:
      print("FATAL ERROR: Not found mask files")
      return

    for mask_file in mask_files:
      basename = os.path.basename(mask_file)
      image_file = basename.replace("-d.bmp", ".BMP")

      image_filepath = os.path.join(categorized_input_dir, image_file)
      print("--- image_filepath {}".format(image_filepath))
      image = Image.open(image_filepath)
      w, h = image.size
      rw   = w * self.resize_ratio
      rh   = h * self.resize_ratio
      image = image.resize((rw, rh))
      image_file = image_file.replace(".BMP", ".jpg")
      image_output_filepath = os.path.join(categorized_images_dir, image_file)
      squared_image = self.resize_to_square(image, mask=False)
      # Save the cropped_square_image
      cropped = self.crop_image(squared_image)
      expanded = cropped.resize((expand, expand))
      expanded.save(image_output_filepath)
      print("--- Saved cropped_square_image {}".format(image_output_filepath))

      ##self.augment(squared_image, categorized_images_dir, image_file)
      self.augment(squared_image, categorized_images_dir, image_file,expand)
   
      print("--- mask_file {}".format(mask_file)) 

      mask  = Image.open(mask_file).convert("RGB")
      w, h = mask.size
      rw   = w * self.resize_ratio
      rh   = h * self.resize_ratio
      mask = mask.resize((rw, rh))
      xmask = self.create_mono_color_mask(mask, mask_color= mask_color)
   
      # Blur mask 
      if self.blur_mask:
        print("---blurred ")
        xmask = xmask.filter(ImageFilter.BLUR)
      
      if debug:
        xmask.show()
        input("XX")   
      out_mask_file = image_file
      mask_output_filepath = os.path.join(categorized_masks_dir, out_mask_file)

      squared_mask = self.resize_to_square(xmask, mask=True)
      cropped_mask = self.crop_image(squared_mask)
      expanded_mask = cropped_mask.resize((expand, expand))
      expanded_mask.save(mask_output_filepath)

      print("--- Saved cropped_squared_mask {}".format(mask_output_filepath))
      #self.augment(squared_mask, categorized_masks_dir, out_mask_file)
      self.augment(squared_mask, categorized_masks_dir, out_mask_file, expand)


  def create_mono_color_mask(self, mask, mask_color=(255, 255, 255)):
    rw, rh = mask.size    
    xmask = Image.new("RGB", (rw, rh))
    #print("---w {} h {}".format(rw, rh))

    for i in range(rw):
      for j in range(rh):
        color = mask.getpixel((i, j))
        (r, g, b) = color
        # If color is blue
        if b == 255:
          xmask.putpixel((i, j), mask_color)

    return xmask
  
GENERATOR = "generator"
MASKCOLOR = "maskcolor"

if __name__ == "__main__":
  try:
    config_file = "./image_mask_generator.config"
    if len(sys.argv) == 2:
      config_file = sys.argv[1]
    if not os.path.exists(config_file):
      raise Exception("Not found your coonfiguration file")
    
    config = ConfigParser(config_file)
    categories_colors = [
      ["carcinoma_in_situ",   (255,    0,   0)],
      ["light_dysplastic",    (  0,  255,   0)],
      ["moderate_dysplastic", (  0,    0, 255)],
      ["normal_columnar",     (255,  255,   0)],
      ["normal_intermediate", (255,    0, 255)],
      ["normal_superficiel",  (  0,  255, 255)],
      ["severe_dysplastic",   (255,  255, 255)],
    ]
    base_dir   = config.get(GENERATOR, "base_dir", dvalue="./New database pictures")
    
    output_dir = config.get(GENERATOR, "output_dir", dvalue="./Smear2005-master")

    # 
    resize    = config.get(GENERATOR, "resize",   dvalue=312)
    cropsize  = config.get(GENERATOR, "cropsize", dvalue=128)
    expand    = config.get(GENERATOR, "expand",   dvalue=512)
    
    if cropsize >= resize:
      raise Exception("Error: cropsize < resize")
    seamless_cloning = config.get(GENERATOR, "seamless_cloning", dvalue=False)

    dataset = ImageMaskDatasetGenerator( resize,  cropsize, seamless_cloning)
    for category_color in categories_colors:
      [category, color] = category_color
      mask_color  = config.get(MASKCOLOR, category, dvalue=color)

      categorized_input_dir  = os.path.join(base_dir, category)
      categorized_output_dir = os.path.join(output_dir, category)
      categorized_images_dir = os.path.join(categorized_output_dir, "images")
      categorized_masks_dir  = os.path.join(categorized_output_dir, "masks")
      
      dataset.create(categorized_input_dir, mask_color, categorized_images_dir, categorized_masks_dir, expand)

  except:
    traceback.print_exc()
    pass

"""
INPUT
./New database pictures
├─carcinoma_in_situ
├─light_dysplastic
├─moderate_dysplastic
├─normal_columnar
├─normal_intermediate
├─normal_superficiel
└─severe_dysplastic



OUPUT
./Smear2005-master
├─carcinoma_in_situ
│  ├─images
│  └─masks
├─light_dysplastic
│  ├─images
│  └─masks
├─moderate_dysplastic
│  ├─images
│  └─masks
├─normal_columnar
│  ├─images
│  └─masks
├─normal_intermediate
│  ├─images
│  └─masks
├─normal_superficiel
│  ├─images
│  └─masks
└─severe_dysplastic
    ├─images
    └─masks
"""