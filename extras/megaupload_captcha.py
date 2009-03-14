#!/usr/bin/python
"""
Decode the 4-rotated-bold-characters captcha used in Megaupload since 2009/03/13
"""
import string
import os
import sys
from StringIO import StringIO

# Third-party modules
from PIL import Image, ImageFont, ImageDraw

def debug(line, linefeed=True, stream=sys.stderr):
    """Write line to standard error."""
    stream.write(str(line)+("\n" if linefeed else ""))
    stream.flush()
    
def get_at(lst, nfield):
    """Return nfield of lst."""
    return [x[nfield] for x in lst]

def substract_images(i1, i2, pos1):
    """Substract (XOR) i2 from i1 and return a new image."""
    i3 = i1.copy()
    ip1, ip2, ip3 = map(load_pixels, [i1, i2, i3])
    width1, height1 = i1.size
    width2, height2 = i2.size
    ox, oy = pos1
    for x in range(min(width2, width1 - ox)):
        for y in range(min(height2, height1 - oy)):
            val1 = ip1[ox+x, oy+y]
            val2 = ip2[x, y]
            ip3[ox+x, oy+y] = (255 if val1 == val2 else 0)
    return i3

def load_pixels(image):
    """Load pixel-access object for image"""
    ipimage = image.load()
    if image.im: 
        # A hack, http://osdir.com/ml/python.image/2008-03/msg00011.html
        return image.im.pixel_access(image.readonly)
    return ipimage
        
def compare_images(i1, i2):
    """Compare two images and return difference error."""
    ip1, ip2 = map(load_pixels, [i1, i2])
    width, height = i1.size
    error = 0
    for x in range(width):
        for y in range(height):
            val1 = ip1[x, y]
            val2 = ip2[x, y]
            error += (1.0 if val1 != val2 else 0.0)
    return float(error) / (width * height)
    
def open_image(path):
    """Open image and return a B&W PIL.Image object.""" 
    transform = lambda x: (x != 0) and 255 or 0
    image = Image.open(path).convert("L").point(transform)
    return image

def crop_image(image, box=None):
    """Return cropped image."""
    return image.crop(box)
        
def autocrop_image(image):
    """Return a cropped image."""
    return crop_image(image, image.getbbox())

def build_chars(fontfile, fontsize, excluded_chars):
    """Return a dictionary of (char, image) pairs for [A-Z0-9]."""
    font = ImageFont.truetype(fontfile, fontsize)
    chars = {}
    for char in string.uppercase + string.digits:
        if char in excluded_chars:
            continue
        image = Image.new("L", (2*fontsize, 2*fontsize), 0)
        draw = ImageDraw.Draw(image)    
        draw.text((0, 0), char, font=font, fill=255)
        chars[char] = autocrop_image(image)
    return chars

def invert_image(image):
    """Invert B&W image."""
    return image.point(lambda x: (0 if x else 255))

def rotate_and_crop(image, angle):
    """Rotate, crop and invert an image."""
    return invert_image(autocrop_image(image.rotate(angle, expand=True)))
  
def get_errors(image, chars, zones):
    """Compare an image against a dictionary of chars."""
    image_width, image_height = image.size
    for char, char_image in sorted(chars.iteritems(), key=lambda (k, v): k):
        debug(".", linefeed=False)
        zones2 = ([zones[0], zones[-1]] if len(zones) > 2 else zones[:])
        for (xstart, xend), (angle_start, angle_end) in zones2:
            for angle in range(angle_start, angle_end+1, 2):
                char_image_rotated = rotate_and_crop(char_image, angle)
                char_width, char_height = char_image_rotated.size
                y = max(0, (image_height - char_height) / 2)
                for x in range(xstart, xend+1, 1):
                    cropped_image = crop_image(image, 
                        (x, y, x+char_width, y+char_height))
                    error = compare_images(char_image_rotated, cropped_image)
                    #print error, char, (x, y), angle
                    #debug_image(substract_images(image, char_image_rotated, (x, y)))
                    #sys.stdin.read(1)
                    yield (error, char, (x, y), angle)                        
    debug("")

def debug_image(image, step=1, stream=sys.stderr):
    """Output image to stream (standard error by default)."""
    ip = image.load()
    width, height = image.size
    for y in range(0, height, step):
        for x in range(0, width, step):
            debug("*" if ip[x, y] == 0 else " ", stream=stream, linefeed=False)
        debug("", stream=stream)

def build_chars_from_image(fontimagefile, excluded_chars):
    """Return a dictionary of (char, image) pairs for [A-Z0-9]."""
    fi = Image.open(fontimagefile)
    char_offset_x, char_offset_y = 16, 16
    char_width, char_height = 72, 72  
    width, height = 711.0/8.0, 1699.0/20.0
    chars = {}
    info = zip(string.digits, range(17, 26+1)) + \
      zip(string.uppercase, range(34, 59+1))
    for char, index in info:
        if char in excluded_chars:
            continue
        row, col = divmod(index, 8)
        x = int(col * width)
        y = int(row * height)  
        image = crop_image(fi, (x + char_offset_x, y + char_offset_y, 
            x + char_offset_x + char_width, y + char_offset_x + char_height))
        chars[char] = autocrop_image(invert_image(image.convert("L")))
    return chars
            
def decode_megaupload_captcha(captcha_imagefile, chars):
    """Return decoded captcha string."""
    image = open_image(captcha_imagefile)
    width, height = image.size
    zones = [
        [(0, 5), (-30, -15)],
        [(int(width/4.0 - 10), int(width/4.0 + 10)), (15, 30)],
        [(int(2.0*width/4.0 - 10), int(2.0*width/4.0 + 10)), (-30, -15)],
        [(int(3.0*width/4.0 - 10), int(3.0*width/4.0 + 10)), (15, 30)],
    ]                
    captcha_length = 4    
    debug_image(image, 2)
    result = []
    while len(result) < captcha_length:
        debug("iteration %d/%d " % (len(result)+1, captcha_length), False)
        min_info = min(get_errors(image, chars, zones))
        min_error, char, pos, angle = min_info
        result.append(min_info)
        debug(min_info)
        x, y = pos        
        for index, ((xstart, xend), (angle_start, angle_end)) in enumerate(zones):
            if xstart <= x <= xend:
                del zones[index]
                break
        char_image_rotated = rotate_and_crop(chars[char], angle)
        image = substract_images(image, char_image_rotated, pos)
        #debug_image(image)
        
    sorted_by_position = sorted(result, key=lambda x: x[2])
    errors = sum(get_at(sorted_by_position, 0)) / 4.0
    captcha = "".join(s[0] for s in get_at(sorted_by_position, 1)).upper()
    debug((errors, captcha))
    return captcha

def load_psyco():
    try:
        import psyco
        psyco.full()
    except ImportError:
        debug("Warning: install python-pysco to speed up the OCR")        

def main(args):
    import optparse
    usage = """usage: megaupload_captcha [OPTIONS] IMAGE"""
    parser = optparse.OptionParser(usage)
    parser.add_option('-q', '--quiet', dest='quiet',
          action="store_true", default=False, help='Be quiet')
    options, args0 = parser.parse_args(args)
    if not args0:
        parser.print_help()
        return 1
    load_psyco()
    if options.quiet:
        global debug
        debug = lambda *args, **kwargs: None
    captcha_file = StringIO(open(args0[0]).read())
    fontfile = os.path.join(os.path.dirname(sys.argv[0]), "delargo_dt_black.png")
    chars = build_chars_from_image(fontfile, excluded_chars="ILJ")    
    print decode_megaupload_captcha(captcha_file, chars)
                    
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))