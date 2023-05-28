"""
Not all 2020 census blocks nest inside 2022 EPC precincts due to obsolence of the TIGER shapefile and state statute to
avoid spliting residential parcels between legislative districts.

This is the process for generating the block assignment file.

Post-process a QGIS attribute table of the intersection of:
  1) EPC 2020 precincts (Precinct.zip) layer
      Link: https://assets-admin.elpasoco.com/wp-content/uploads/it-gis/Precinct.zip
  2) TIGER shapefile for EPC (tl_2020_08041_tabblock20.zip) layer
      Link: https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/08_COLORADO/08041/tl_2020_08041_tabblock20.zip
  3) In QGIS, Vector -> Geoprocessing Tools -> Intersection
      Input layer: Precinct[], Overlay layer: tl_2020_0804_tabblocks20 [EPSG:4269]
  3) In QGIS, open attribute table for the intersection, click field calculator, and add $area expression field called ZOVERLAP
      See: https://gis.stackexchange.com/questions/193362/calculate-areas-of-overlapping-polygons-from-two-shapefiles
  4) Save attribute table (unofficial_precinct_attribute_table_from_qgis.csv)
  5) Run this program and output the BAF (precinct_block_assign_file.csv)
"""

import locale
import csv

def remove_block_duplicates(precinct_attribute_table_file, block_assignment_file):
    block_to_precinct = dict()
    blocks_not_split = 0
    blocks_split = 0
    blocks_total = 0
    with open(precinct_attribute_table_file, 'r') as fp1:
        csvreader = csv.DictReader(fp1)
        for row in csvreader:
            blocks_total += 1
            zoverlap = float(row['ZOVERLAP'])
            # print(row['PRECINCT'], row['GEOID20'])
            if row['GEOID20'] in block_to_precinct:
                # Duplicate. This precinct was split between two or more census blocks
                existing_precinct= block_to_precinct[row['GEOID20']]['precinct']
                existing_zoverlap = block_to_precinct[row['GEOID20']]['zoverlap']
                # print(f"Duplicate/split census block found: {row['GEOID20']=},{row['PRECINCT']=},{zoverlap},{existing_precinct=},{existing_zoverlap=}")
                if existing_zoverlap < zoverlap:
                    # Replace with the overlap of the largest area intersection
                    block_to_precinct[row['GEOID20']] = {'precinct': row['PRECINCT'], 'zoverlap': zoverlap}
                blocks_split += 1
            else:
                # First block seen to assign to the precinct
                block_to_precinct[row['GEOID20']] = {'precinct': row['PRECINCT'], 'zoverlap': zoverlap}
                blocks_not_split += 1

    dedup_blocks = len(block_to_precinct.keys())
    # Print some stats
    print(f"Summary: {blocks_total=},{blocks_not_split=},{blocks_split=},{dedup_blocks=}")

    # Emit the block assignment file
    with open(block_assignment_file, 'w') as fp2:
        fp2.write("BLOCK,PRECINCT\n")
        for block_number in block_to_precinct.keys():
            precinct_number = block_to_precinct[block_number]['precinct']
            fp2.write(f"{block_number},{precinct_number}\n")


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')  # For parsing numbers with comma separators

    # Input: unofficial_precinct_attribute_table_from_qgis.csv (created by QGIS Intersection Geoprocessing tool)
    # Output: precinct_block_assign_file.csv
    remove_block_duplicates("./epc_files/unofficial_precinct_attribute_table_from_qgis.csv", "./epc_files/precinct_block_assign_file.csv")
