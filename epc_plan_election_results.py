"""
This script processes election results for El Paso County by redistricting plan.

The election results are produced for 2 sets of races:
  1) Statewide races (Governor, SOS, etc.)
  2) Countywide races (Sheriff, C&R, Assessor, etc.)
"""
import os
import locale
import csv
import re
import pprint
from collections import OrderedDict

# This is the configuration for the matcher for El Paso County commissioner districts
district_types = {
    'elpaso_commissioner': {
        'districts': tuple(range(1, 6)),   # 5 commissioners
        'precinct_match_group_number': 3,  # for regex
        'county_number': 21,               # El Paso County
    },
}

# Define the statewide races for each year
statewide_races_by_year = {
    2022: {
        'governor': r'Governor/Lieutenant Governor',
        'sec_of_state': r'Secretary of State',
        'treasurer': r'State Treasurer',
        'attorney_general': r'Attorney General',
        'boe_at_large': r'State Board of Education Member - At Large',
    },
}

# SOS election results column names changed over time for some reason
sos_csv_column_names = {
    2022: {
        'office_column_name': 'Office',
        'vote_count_column_name': 'Votes',
    },
}

def statewide_race_matcher(year, row):
    for race in statewide_races_by_year[year].keys():
        if row[sos_csv_column_names[year]['office_column_name']] == statewide_races_by_year[year][race]:
            # Return 'us_president' or 'us_senator'
            return race
    return None

def init_statewide_results_dict(year):
    """
    Initialize statewide races by district with dictionary of party counts by Democrat, Republican, and Other
    {
    'us_president':
        {
        'elpaso_commissioner': {
            1: {'democrat': 0, ...},
            2: {'democrat': 0, ...}},
            3: ...
    'us_senate': ...,
    }
    """
    results = dict()
    for race in statewide_races_by_year[year].keys():
        results[race] = dict()
        for district_type in district_types.keys():
            district_results = OrderedDict()
            for district in district_types[district_type]['districts']:
                district_results[district] = dict(county_list=[], democrat=0, republican=0, other=0)
            results[race][district_type] = district_results
    return results

def precinct_number_matcher(precinct_number, year, county, district_block_assignment, precinct_block_assignment):
    # https://www.sos.state.co.us/pubs/elections/FAQs/VoterFAQs.html
    # • First digit – Congressional District
    # • Second and third digits – State Senate District
    # • Fourth and fifth digits – State Representative District
    # • Sixth and seventh digits – County Number
    # • Last three digits – Precinct

    # County Number (ID #) can be found here: https://www.sos.state.co.us/pubs/elections/Resources/files/CountyClerkRosterWebsite.pdf

    matches = re.match(r'^(\d{1})(\d{2})(\d{2})(\d{2})(\d{3})$', precinct_number)
    if matches:
        # Need to lookup the group number, 0 = Congressional District, 1 = State Senate, 2 = State Representative, 3 = County Number
        precinct_dict = dict()
        for district_type in district_types.keys():
            group_number = district_types[district_type]['precinct_match_group_number']
            if 'county_number' in district_types[district_type]:
                # This is an EPC commissioner district (EPC county number is 21)
                # But code is generalized to support any county with commissioner districts
                if district_types[district_type]['county_number'] == int(matches.groups()[group_number]):
                    # Lookup commissioner district given the 3 digit precinct number
                    short_precinct_number = int(matches.groups()[4])
                    try:
                        # Lookup block by short precinct number
                        block = precinct_block_assignment[short_precinct_number]
                    except KeyError as ke:
                        print(f"Unhandled precinct_number: {short_precinct_number=} {precinct_number=}")
                        block = None
                    try:
                        # Lookup district by block
                        precinct_dict[district_type] = district_block_assignment[block]
                    except KeyError as ke:
                        print(f"Unhandled block number: {block=} {precinct_number=}")
                        precinct_dict[district_type] = None
                else:
                    precinct_dict[district_type] = None
            else:
                # All other statewide districts
                precinct_dict[district_type] = int(matches.groups()[group_number])
        # Example: {'us_house': 1, 'co_senate': 2, 'co_house': 3, 'co_county': 4, 'elpaso_commissioner': 5}
        return precinct_dict
    elif precinct_number == 'Provisional':
        raise NotImplementedError("Provisional precincts not supported")

def write_csv_files(year, results, plan_name):
    """
    Write the results for each year and statewide office by district type
    For 2022, there were 6 statewide offices
    """
    # Recursively create results directory
    outdir = f"./epc_election_data/{plan_name}"
    os.makedirs(outdir, exist_ok = True)

    # Generate results
    header = ('district', 'counties', 'democrat', 'republican', 'other')
    for race in results.keys():
        for district_type in results[race].keys():
            csvout = f"{outdir}/{year}_{race}_by_{district_type}.csv"
            print(f"Writing {csvout}")
            with open(csvout, 'w') as fp2:
                csvwriter = csv.DictWriter(fp2, fieldnames=header, extrasaction='ignore')
                csvwriter.writeheader()
                for district_number in results[race][district_type].keys():
                    row = results[race][district_type][district_number]
                    row['district'] = district_number
                    row['counties'] = ' - '.join(row['county_list'])
                    csvwriter.writerow(row)


def process_precinct_level_results(the_plan):
    # First, initialize the block to district number mapping
    # block number -> district number
    district_block_assignment = dict()
    with open(the_plan['district_block_assignment_file'], 'r') as fp1:
        csvreader = csv.DictReader(fp1)
        for row in csvreader:
            # Determine the column headings 
            block_header = list(row.keys())[0]  # BLOCK or GEOID20
            district_header = list(row.keys())[1]  # DISTRICT or District
            district_block_assignment[row[block_header]] = int(row[district_header])
    # pp = pprint.PrettyPrinter()
    # pp.pprint(district_block_assignment)
    # return

    # Second, initialize the block to precinct number mapping
    # precinct number -> block number
    precinct_block_assignment = dict()
    with open(the_plan['precinct_block_assignment_file'], 'r') as fp1:
        csvreader = csv.DictReader(fp1)
        for row in csvreader:
            # Determine the column headings 
            block_header = 'BLOCK'
            precinct_header = 'PRECINCT'
            precinct_block_assignment[int(row[precinct_header])] = row[block_header]
    # pp = pprint.PrettyPrinter()
    # pp.pprint(precinct_block_assignment)
    # return

    year = the_plan['year']

    # Third, initialize and populate the election results dict
    results = init_statewide_results_dict(year)
    # pp = pprint.PrettyPrinter()
    # pp.pprint(results)

    with open(the_plan['statewide_election_results'], 'r') as fp:
        csvreader = csv.DictReader(fp)
        for row in csvreader:
            # race_match is 'us_president' or 'us_senator'
            race_match = statewide_race_matcher(year, row)
            if race_match:
                # district_numbers is a dict parsed from Precinct: {'us_house': 1, 'co_senate': 2, 'co_house': 3, 'co_county': 4}
                district_numbers = precinct_number_matcher(row['Precinct'], year, row['County'], district_block_assignment, precinct_block_assignment)
                # district_type will be 'us_house', 'co_senate', 'co_house', 'co_county'
                for district_type in results[race_match]:
                    # 2020: Democratic Party, Republican Party
                    # 2022: DEM, REP
                    if row['Party'] in ['Democratic Party', 'DEM']:
                        party = 'democrat'
                    elif row['Party'] in ['Republican Party', 'REP']:
                        party = 'republican'
                    else:
                        party = 'other'
                    # District_number depends on type
                    district_number = district_numbers[district_type]
                    if district_number is None:
                        # If district_type is 'elpaso_commissioner' but the precinct is not in EPC, then skip
                        continue
                    # Update vote totals for this district
                    try:
                        results_row = results[race_match][district_type][district_number]
                    except KeyError as ke:
                        print(f"KeyError: {district_type=} {district_number=}")
                        raise ke
                    results_row[party] += locale.atoi(row[sos_csv_column_names[year]['vote_count_column_name']])
                    # Update county list for this district
                    if row['County'] not in results_row['county_list']:
                        results_row['county_list'].append(row['County'])
        # After processing all rows in the precinct level CSV, output the results by district
        # pp = pprint.PrettyPrinter()
        # pp.pprint(results)
        write_csv_files(year, results, the_plan['plan_name'])


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')  # For parsing numbers with comma separators

    # Current commissioner districts
    the_plan = {
        'year': 2022,
        'plan_name': 'current',
        'statewide_election_results': 'sos_files/2022GeneralPrecinctLevelResultsPublic.csv',
        'countywide_election_results': None,
        'district_block_assignment_file': 'epc_files/epc_commissioner_districts_2022.csv',  # Changes with each plan
        'precinct_block_assignment_file': 'epc_files/precinct_block_assign_file.csv',  # Fixed for all plans
    }

    # Another plan
    # the_plan = {
    #     'year': 2022,
    #     'plan_name': 'myplan',
    #     'statewide_election_results': 'sos_files/2022GeneralPrecinctLevelResultsPublic.csv',
    #     'countywide_election_results': None,
    #     'district_block_assignment_file': 'plans/block-assignments-myplan.csv',  # Changes with each plan
    #     'precinct_block_assignment_file': 'epc_files/precinct_block_assign_file.csv',  # Fixed for all plans
    # }


    process_precinct_level_results(the_plan)
