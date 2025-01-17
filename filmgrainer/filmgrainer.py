# Filmgrainer - by Lars Ole Pontoppidan - MIT License
import numpy as np

from PIL import Image, ImageFilter
import os 

import filmgrainer.graingamma as graingamma
import filmgrainer.graingen as graingen


def _grainTypes(typ):
    # After rescaling to make different grain sizes, the standard deviation
    # of the pixel values change. The following values of grain size and power
    # have been imperically chosen to end up with approx the same standard 
    # deviation in the result:
    if typ == 1:
        return (0.8, 63) # more interesting fine grain
    elif typ == 2:
        return (1, 45) # basic fine grain
    elif typ == 3:
        return (1.5, 50) # coarse grain
    elif typ == 4:
        return (1.6666, 50) # coarser grain
    else:
        raise ValueError("Unknown grain type: " + str(typ))

# Grain mask cache
MASK_CACHE_PATH = "/tmp/mask-cache/"

def _getGrainMask(img_width:int, img_height:int, saturation:float, grayscale:bool, grain_size:float, grain_gauss:float, seed):
    if grayscale:
        str_sat = "BW"
        sat = -1.0 # Graingen makes a grayscale image if sat is negative
    else:
        str_sat = str(saturation)
        sat = saturation

    filename = MASK_CACHE_PATH + "grain-%d-%d-%s-%s-%s-%d.png" % (
        img_width, img_height, str_sat, str(grain_size), str(grain_gauss), seed)
    if os.path.isfile(filename):
        print("Reusing: %s" % filename)
        mask = Image.open(filename)
    else:
        mask = graingen.grainGen(img_width, img_height, grain_size, grain_gauss, sat, seed)
        print("Saving: %s" % filename)
        if not os.path.isdir(MASK_CACHE_PATH):
            os.mkdir(MASK_CACHE_PATH)
        mask.save(filename, format="png", compress_level=1)
    return mask


def process(file_in:str, scale:float, src_gamma:float, grain_power:float, shadows:float,
            highs:float, grain_type:int, grain_sat:float, gray_scale:bool, sharpen:int, seed:int, file_out=None):
            
    print("Loading: " + file_in)
    img = Image.open(file_in).convert("RGB")
    org_width = img.size[0]
    org_height = img.size[1]
    
    if scale != 1.0:
        print("Scaling source image ...")
        img = img.resize((int(org_width / scale), int(org_height / scale)),
                          resample = Image.LANCZOS)
    
    img_width = img.size[0]
    img_height = img.size[1]
    print("Size: %d x %d" % (img_width, img_height))

    print("Calculating map ...")
    map = graingamma.Map.calculate(src_gamma, grain_power, shadows, highs)
    # map.saveToFile("map.png")

    print("Calculating grain stock ...")
    (grain_size, grain_gauss) = _grainTypes(grain_type)
    mask = _getGrainMask(img_width, img_height, grain_sat, gray_scale, grain_size, grain_gauss, seed)

    #mask_pixels = mask.load()
    #img_pixels = img.load()

    np_img = np.array(img)
    np_mask = np.array(mask)
           
    # Instead of calling map.lookup(a, b) for each pixel, use the map directly:
    lookup = map.map

    #if gray_scale:
    #    print("Film graining image ... (grayscale)")
    #    for y in range(0, img_height):
    #        for x in range(0, img_width):
    #            m = mask_pixels[x, y]
    #            (r, g, b) = img_pixels[x, y]
    #            gray = int(0.21*r + 0.72*g + 0.07*b)
    #            #gray_lookup = map.lookup(gray, m)
    #            gray_lookup = lookup[gray, m]
    #            img_pixels[x, y] = (gray_lookup, gray_lookup, gray_lookup)
    #else:
    #    print("Film graining image ...")
    #    for y in range(0, img_height):
    #        for x in range(0, img_width):
    #            (mr, mg, mb) = mask_pixels[x, y]
    #            (r, g, b) = img_pixels[x, y]
    #            r = lookup[r, mr]
    #            g = lookup[g, mg]
    #            b = lookup[b, mb]
    #            img_pixels[x, y] = (r, g, b)

    img_height, img_width = np_img.shape[:2]

    print("Film graining image ...")
    if gray_scale:
        # Convert to grayscale using vectorized operation
        gray_img = np.dot(np_img[...,:3], [0.21, 0.72, 0.07]).astype(int)
        # Apply lookup table using advanced indexing
        gray_lookup = lookup[gray_img, np_mask]
        np_img = np.stack([gray_lookup] * 3, axis=-1)
    else:
        # Apply lookup table using advanced indexing for each channel
        r_lookup = lookup[np_img[:,:,0], np_mask[:,:,0]]
        g_lookup = lookup[np_img[:,:,1], np_mask[:,:,1]]
        b_lookup = lookup[np_img[:,:,2], np_mask[:,:,2]]
        np_img = np.stack([r_lookup, g_lookup, b_lookup], axis=-1)

    img = Image.fromarray(np_img.astype('uint8'))
                
    if scale != 1.0:
        print("Scaling image back to original size ...")
        img = img.resize((org_width, org_height), resample = Image.LANCZOS)
    
    if sharpen > 0:
        print("Sharpening image: %d pass ..." % sharpen)
        for x in range(sharpen):
            img = img.filter(ImageFilter.SHARPEN)

    print("Saving: " + file_out)
    img.save(file_out, quality=97)
