# Copyright 2017 Sidewalk Labs | https://www.apache.org/licenses/LICENSE-2.0

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import pandas
import requests


CONTROLS = {
    'hh_size': {
        'count': [
            'B11016_010E',
            'B11016_003E', 'B11016_011E',
            'B11016_012E', 'B11016_004E',
            'B11016_005E', 'B11016_006E', 'B11016_007E', 'B11016_008E',
            'B11016_013E', 'B11016_014E', 'B11016_015E', 'B11016_016E'
        ],
        '1': ['B11016_010E'],
        '2': ['B11016_003E', 'B11016_011E'],
        '3': ['B11016_012E', 'B11016_004E'],
        '4+': [
            'B11016_005E', 'B11016_006E', 'B11016_007E', 'B11016_008E',
            'B11016_013E', 'B11016_014E', 'B11016_015E', 'B11016_016E'
        ],
    },
    'age': {
        # ages 0 - 17
        '0-17': [
            'B01001_003E', 'B01001_004E', 'B01001_005E', 'B01001_006E',
            'B01001_027E', 'B01001_028E', 'B01001_029E', 'B01001_030E'
        ],
        # ages 18 - 34
        '18-34': [
            'B01001_007E', 'B01001_008E', 'B01001_009E', 'B01001_010E',
            'B01001_011E', 'B01001_012E', 'B01001_031E', 'B01001_032E',
            'B01001_033E', 'B01001_034E', 'B01001_035E', 'B01001_036E'
        ],
        # ages 35 - 64
        '35-64': [
            'B01001_013E', 'B01001_014E', 'B01001_015E', 'B01001_016E',
            'B01001_017E', 'B01001_018E', 'B01001_019E', 'B01001_037E',
            'B01001_038E', 'B01001_039E', 'B01001_040E', 'B01001_041E',
            'B01001_042E', 'B01001_043E'
        ],
        # ages 65+
        '65+': [
            'B01001_020E', 'B01001_021E', 'B01001_022E', 'B01001_023E',
            'B01001_024E', 'B01001_025E', 'B01001_044E', 'B01001_045E',
            'B01001_046E', 'B01001_047E', 'B01001_048E', 'B01001_049E'
        ],
    }
}


CONTROL_NAMES = tuple(i for cat in CONTROLS.keys()
                      for i in CONTROLS[cat].keys())


class CensusFetchException(Exception):
    pass


class Marginals(object):

    def __init__(self, data):
        self.data = data

    @staticmethod
    def _fetch_from_census(
        census_key, field_key_list, tract_key, state_key, county_key
    ):
        controls_str = ','.join(field_key_list)
        query = ('http://api.census.gov/data/2015/acs5?get={}'
                 '&for=tract:{}&in=state:{}+county:{}&key={}'
                 ).format(controls_str, tract_key, state_key,
                          county_key, census_key)
        try:
            encoded_response = requests.get(query)
            response = encoded_response.json()
        except Exception:
            print('failed to load marginals for query:\n{}\n'.format(query))
            print('response:\n{}'.format(encoded_response.text))
            raise CensusFetchException()
        control_keys = response[0]
        control_counts = response[1]
        full_controls = dict(zip(control_keys, control_counts))
        return full_controls

    @staticmethod
    def from_census_data(puma_tract_mappings, census_key, pumas=None):
        """Fetch marginal sums from the census API.

        Args:
            puma_tract_mappings (dict): mappings of the form {
                STATEFP -> state id,
                COUNTYFP -> county id
                PUMA5CE -> puma id
                TRACTCE -> tract id
            }
                of PUMAs to fetch data for

            census_key (unicode): census API key

            pumas (iterable of unicode): a list of pumas to fetch for.  If the
                parameter is not passed in will fetch for all pumas in
                puma_tract_mappings

        Returns:
            Marginals: marginals fetched from the census API

        """
        data = []

        for line in puma_tract_mappings:
            if pumas is not None and line['PUMA5CE'] not in pumas:
                continue
            state_key = line['STATEFP']
            tract_key = line['TRACTCE']
            puma_key = line['PUMA5CE']
            county_key = line['COUNTYFP']
            print('Fetching tract {}'.format(tract_key))
            controls_dict = {}
            success = True
            for _, control_cat in CONTROLS.items():
                key_list = [key for sublist in list(
                    control_cat.values()) for key in sublist]
                try:
                    full_controls = Marginals._fetch_from_census(
                        census_key, key_list, tract_key, state_key, county_key
                    )
                except CensusFetchException:
                    print('Skip puma {} tract {}'.format(puma_key, tract_key))
                    success = False
                    break
                selected_controls = {
                    key: full_controls[key] for key in full_controls.keys()
                    if key not in ['state', 'public use microdata area']
                }

                for sum_key, sum_cat in control_cat.items():
                    counts = sum([int(selected_controls[key]) for key in sum_cat])
                    controls_dict[sum_key] = counts
            if success:
                output = [state_key, county_key, puma_key, tract_key]
                for control_name in CONTROL_NAMES:
                    output.append(str(controls_dict[control_name]))
                data.append(output)

        columns = ['STATEFP', 'COUNTYFP', 'PUMA5CE',
                   'TRACTCE'] + list(CONTROL_NAMES)
        return Marginals(pandas.DataFrame(data, columns=columns))

    @staticmethod
    def from_csv(infile, puma=None):
        """Load marginals from file.

        Args:
            infile (unicode): path to csv

        Returns:
            Marginals: marginals fetched from the census API

        """
        data = pandas.read_csv(infile)
        if puma is not None:
            data = data[data['PUMA5CE'] == int(puma)]
        return Marginals(data)

    def write(self, outfile):
        """Write marginals to the given file

        Args:
            outfile (unicode): path to write to

        """
        self.data.to_csv(outfile)
