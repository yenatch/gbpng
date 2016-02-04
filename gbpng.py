#!/bin/python

import png
from math import sqrt
import argparse
import os

def read_png(filename):
    """
    A wrapper for png.Reader.asRGBA8.
    """
    return png.Reader(open(filename)).asRGBA8()

def write_png(filename, png_data):
    """
    A wrapper for png.Writer.write.
    """
    width, height, px_map, info = png_data
    w = png.Writer(width=width, height=height, compression=9, **info)
    with open(filename, 'wb') as f:
        w.write(f, px_map)

def read_gb(filename):
    return bytearray(open(filename).read())

def write_gb(filename, data):
    open(filename, 'wb').write(bytearray(data))

def pad_palette(palette):
    """
    Pad out smaller palettes with greyscale colors.
    """
    greyscale = [
        (0xff, 0xff, 0xff, 0xff), # white
        (0x00, 0x00, 0x00, 0xff), # black
        (0x55, 0x55, 0x55, 0xff), # grey
        (0xaa, 0xaa, 0xaa, 0xff), # gray
    ]
    if not palette:
        return sorted(greyscale, reverse=True)

    for hue in greyscale:
        if len(palette) >= 4:
            break
        if hue not in palette:
            palette += [hue]
    return palette

def get_unaligned_image_padding(width, height, tile_width=8, tile_height=8):
    """
    Return values (left, right, top, bottom) to add to dimensions (<width>, <height>) to conform to tile dimensions (<tile_width>, <tile_height>).
    """
    left, right, top, bottom = 0, 0, 0, 0

    pad = width % tile_width
    if pad and width > tile_width:
        left = pad / 2 + pad % 2
        right = pad / 2

    pad = height % tile_height
    if pad and height > tile_height:
        top = pad / 2 + pad % 2
        bottom = pad / 2

    return left, right, top, bottom

def png_to_gb(png_data):
    """
    Return a planar 2bpp graphic and its palette, given a tuple containing png data.
    """
    width, height, rgba, info = png_data

    palette = info.get('palette')
    palette = pad_palette(palette)

    # Pad out dimensions to 8px alignment.
    left, right, top, bottom = get_unaligned_image_padding(width, height)
    width += left + right
    height += top + bottom
    pad = [0]
    left *= pad
    right *= pad
    top *= pad
    bottom *= pad

    # Map pixels to quaternary color ids.
    # Combine with the padding step.
    qmap = []
    qmap += width * top
    for line in rgba:
        qmap += left
        for i in xrange(0, len(line), 4):
            color = tuple(line[i:i+4])
            index = palette.index(color)
            qmap += [index]
        qmap += right
    qmap += width * bottom

    # Convert to planar 2bpp.
    planar = bytearray()
    for y in xrange(0, height, 8):
        for x in xrange(0, width, 8):
            for tile_y in xrange(8):
                index = (y + tile_y) * width + x
                line = qmap[index:index+8]
                bottom, top = 0, 0
                for i, quad in enumerate(line):
                    bit = 7 - i
                    bottom += (quad & 1) << bit
                    top += ((quad >> 1) & 1) << bit
                planar .append(bottom)
                planar .append(top)

    return planar, palette

def planar_to_tiles(planar):
    """
    Return a list of lists of color indices, given a planar 2bpp graphic.
    """
    tiles = []
    tile = []
    pairs = zip(*[iter(planar)] * 2)
    for i, (bottom, top) in enumerate(pairs):
        for j in xrange(7, -1, -1):
            color = (
                ((bottom >> j) & 1) +
                (((top   >> j) & 1) << 1)
            )
            tile += [color]
        if len(tile) >= 64:
            tiles += [tile]
            tile = []
    return tiles

def gb_to_png(planar, width=None, height=None, palette=None):
    """
    Return a tuple of png data (width, height, lines, info), given a planar 2bpp graphic, and optionally dimensions/palette.
    It is recommended to provide at least one of width or height, or the tiles in the resulting image might not align as intended.
    Providing no palette will create a greyscale image.
    """
    planar = bytearray(planar)
    tiles = planar_to_tiles(planar)

    # Game Boy graphics do not have dimension information.
    if not width:
        if not height:
            width = int(sqrt(len(tiles))) * 8
        else:
            width = (len(tiles) * 8) / height
    if not height:
        height = height or ((len(tiles) * 8) / width) * 8

    palette = pad_palette(palette)

    lines = []
    for y in xrange(height):
        line = []
        tile_y = y / 8
        strip_y = y % 8
        tiles_per_row = width / 8
        for x in xrange(tiles_per_row):
            index = tile_y * tiles_per_row + x
            tile = tiles[index]
            index = strip_y * 8
            strip = tile[index:index+8]
            line += strip
        lines += [line]

    info = {}
    if palette: info['palette'] = palette

    return width, height, lines, info

def gb_2to1(two):
    """
    Convert planar 2bpp image data to 1bpp. Assume images are two colors.
    """
    return two[::2]

def gb_1to2(two):
    """
    Convert 1bpp image data to planar 2bpp (two colors).
    """
    return [b for byte in two for b in byte, byte]

def test_round_trip():
    """
    Turn a predefined 2bpp into a png, then back again, and see if it matches.
    """
    sample_gb = bytearray([0x28, 0x28, 0x0, 0x0, 0x0, 0x8, 0x4, 0x4, 0x0, 0x8, 0x0, 0x0, 0x82, 0x82, 0xfc, 0x7c])
    write_png('_gbpng_test.png', gb_to_png(sample_gb))
    sample_png = read_png('_gbpng_test.png')
    return sample_gb == png_to_gb(sample_png)[0]

def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('filename')
    args = ap.parse_args()
    return args

def main():
    args = get_args()
    filename = args.filename
    image = read_png(filename)
    gb, palette = png_to_gb(image)
    filename = os.path.splitext(filename)[0] + '.2bpp'
    write_gb(filename, gb)

if __name__ == '__main__':
    main()
