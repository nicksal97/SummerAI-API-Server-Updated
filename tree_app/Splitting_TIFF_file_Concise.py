import os
from osgeo import gdal, osr
from PIL import Image

# Open the TIFF file:
# file_path = input('''Enter the file path to the '.tif' file, for example \
# 'Path\\to\\file.tif': ''')
# file_path = '210317 V 2D Bachelorarbeit SL Distr.V Abt. 1.tif'
def tif_main(file_path,folder_path):
    raster = gdal.Open(file_path)

    # Extract the geotransform and print it:
    geo_transform = raster.GetGeoTransform()
    print(f'\nGeoTransform for the file: {geo_transform}')


    # Extract and print the Well-Known Text (WKT) format of the CRS:
    wkt = raster.GetProjection()
    print(f'\nWell-Known Text (WKT) format of the CRS: {wkt}')

    # Initialize the SpatialReference object with the WKT:
    crs = osr.SpatialReference()
    crs.ImportFromWkt(wkt)
    print(f'\nInitialized CRS: {crs.ExportToWkt()}')

    # Check if the units are in meters, if not or unknown, reprojects the
    # raster:
    if crs.GetLinearUnitsName() not in ['meter', 'metre', 'meters', 'metres']:
        print('''\nThe GeoTransform units are not in meters or are unknown.
    Reprojecting raster...''')

        # Determine an appropriate UTM zone for reprojecting:

        # THIS IS A ROUGH ESTIMATION AND SHOULD BE REFINED ACCORDING TO THE
        # RASTER'S LOCATION.
        utm_zone = int((geo_transform[0] + 180) / 6) + 1
        is_northern = geo_transform[3] > 0

        # Create a UTM projection string for reprojection:
        utm_crs = osr.SpatialReference()
        utm_crs.SetUTM(utm_zone, is_northern)
        utm_crs.SetWellKnownGeogCS('WGS84')
        gdal.Warp('static/reprojected.tif', raster, dstSRS=utm_crs.ExportToWkt())

        # Update the raster, 'geo_transform', and WKT with the reprojected
        # versions:
        raster = gdal.Open('static/reprojected.tif')
        # Update 'geo_transform' and 'wkt'
        geo_transform = raster.GetGeoTransform()
        wkt = raster.GetProjection()
        # Update 'crs' with the new WKT
        crs.ImportFromWkt(wkt)


    # Get and print the units of the GeoTransform:
    units = crs.GetLinearUnitsName()
    print(f'''\nThe linear units of the 'GeoTransform' are in: {units}''')


    # Extract xmin and ymax coordinates from the geotransform:
    xmin, ymax = geo_transform[0], geo_transform[3]

    print(f'\nxmin coordinates: {xmin}')
    print(f'\nymax coordinates: {ymax}')


    # Get the resolution in both directions
    raster_resolution_x, raster_resolution_y = geo_transform[1], abs(geo_transform[5])

    print(f'\nResolution in the x direction: {raster_resolution_x} {units}')
    print(f'Resolution in the y direction: {raster_resolution_y} {units}')

    print(f'''The total number of pixels across the width of the
    image or the number of raster in x direction: {raster.RasterXSize}''')


    # Calculate the total length in both directions:
    raster_x_length = raster_resolution_x * raster.RasterXSize
    raster_y_length = raster_resolution_y * raster.RasterYSize

    print(f'\nTotal length in x direction: {raster_x_length} {units}')
    print(f'Total length in y direction: {raster_y_length} {units}')

    print(f'''\nTotal physical size of the raster: \
    {raster_x_length} (x axis) x {raster_y_length} (y axis) {units}''')


    # Define the size of the tiles:
    xsize_tile = float(150)
    ysize_tile = float(150)

    # Ask for the output folder name or set a default one:
    output_folder = folder_path
    os.makedirs(output_folder, exist_ok=True)

    # Calculate the number of tiles in each direction:
    tiles_x = raster_x_length/xsize_tile
    tiles_y = raster_y_length/ysize_tile

    print(f"Number of tiles in x-direction: {round(tiles_x)}")
    print(f"Number of tiles in y-direction: {round(tiles_y)}")

    print(f'''\nTile size will be: {xsize_tile} x {ysize_tile} {units}''')
    print(f'''Your folder name will be: {output_folder}''')


    # Ask the user if they want to proceed with generating TIFF tiles:
    proceed = 'y'

    # Open a text file to write the geo coordinates of each tile:
    with open(os.path.join('static/', '0_Tiles_Geo_Coordinates.txt'),
              'w') as file:

        if proceed == 'y':
            # Generate the coordinates for the tiles:
            xsteps = [xmin + float(xsize_tile) *
                      i for i in range(round(tiles_x)+1)]
            ysteps = [ymax - float(ysize_tile) *
                      i for i in range(round(tiles_y)+1)]

            print(f'\nX coordinates of tiles: {xsteps}')
            print(f'Y coordinates of tiles: {ysteps}')

            # Perform the segmentation and save the tiles:
            for i in range(round(tiles_x)):
                for j in range(round(tiles_y)):
                    tile_xmin, tile_xmax = xsteps[i], xsteps[i + 1]
                    tile_ymax, tile_ymin = ysteps[j], ysteps[j + 1]

                    # Writes each tile details to the text file:
                    file.write(f'''\nFile Name: Segmented_{i}_{j}.tif
    Tile xmin coordinates at top left: {tile_xmin}
    Tile ymin coordinates at top left: {tile_ymax}
    Size of the cut: {xsize_tile} x {ysize_tile} m\n''')

                    print(f'\nTile {i},{j} bounds:')
                    print(f'xmin: {tile_xmin}, xmax: {tile_xmax}')
                    print(f'ymax: {tile_ymax}, ymin: {tile_ymin}')
                    print('\n')

                    tiff_tile_name = os.path.join(output_folder,
                                                  f'Segmented_{i}_{j}.tif')
                    jpg_tile_name = os.path.join(output_folder,
                                                 f'Segmented_{i}_{j}.jpeg')

                    # Use GDAL's Warp function to segment the raster based on
                    # the tile coordinates:
                    gdal.UseExceptions()
                    try:
                        gdal.Warp(tiff_tile_name, raster, outputBounds=(tile_xmin,
                                                                        tile_ymin,
                                                                        tile_xmax,
                                                                        tile_ymax),
                                  dstNodata=-9999)
                        print(f"Successfully warped tile {i}, {j}")
                    except Exception as e:
                        print(f"Error warping tile {i}, {j}: {e}")

                    # Open the TIFF tile, resize and save as JPEG
                    with Image.open(tiff_tile_name) as tile_img:
                        # Convert RGBA to RGB to remove alpha channel:
                        if tile_img.mode == 'RGBA':
                            tile_img = tile_img.convert('RGB')

                        # Resize image to 1000x1000 pixels:
                        tile_img.thumbnail((1000, 1000))

                        # Set the Dots Per Inch (DPI) to 300:
                        tile_img.save(jpg_tile_name, 'JPEG', quality=90,
                                      dpi=(300, 300))

                    print(f'\nTile saved as: {tiff_tile_name} and {jpg_tile_name}')

            # After processing all tiles, deletes the 'reprojected.tif' file if
            # it exists, to avoid conflicts when running this script multiple
            # times:
            reprojected_file_path = 'static/reprojected.tif'
            if os.path.exists(reprojected_file_path):
                try:
                    # Explicitly close the GDAL dataset
                    raster = None
                    # Attempt to remove the file
                    os.remove(reprojected_file_path)
                    print(f"\nRemoved temporary file: {reprojected_file_path}")
                except PermissionError as e:
                    print(f"Could not remove temporary file due to: {e}")
                else:
                    print(f"No temporary file to remove: {reprojected_file_path}")

        elif proceed == 'n':
            print("Operation cancelled. No tiles generated.")
        else:
            print("Invalid input. No tiles generated.")
