#!/usr/bin/env python

import json, os, re
import argparse

from dopy.manager import DoManager

DEFAULT_API_KEY = os.environ.get('DO_APIV2_KEY')

class Inventory(dict):
    def dumps(self):
        return json.dumps(self, sort_keys=True, indent=4, separators=(',', ': '))

    def filter_by(self, key):
        filtered = Inventory()
        try:
            allowed = set(self[key])
        except KeyError:
            return filtered

        # Filter host vars
        hostvars = self['_meta']['hostvars']
        for host in hostvars.keys():
            if host in allowed:
                if '_meta' not in filtered:
                    f_meta = filtered['_meta'] = {'hostvars':{}}
                f_meta['hostvars'][host] = hostvars[host]

        for group in [v for v in self.keys() if v != '_meta']:
            for host in self[group]:
                if host in allowed:
                    if group not in filtered:
                        filtered[group] = []
                    filtered[group].append(host)

        return filtered


class DoInventory(Inventory):
    def __init__(self, api_key=DEFAULT_API_KEY, public=True):
        self.api_key = api_key
        self.address_type = 'public' if public else 'private'
        self.get_droplets()

    @property
    def do(self):
        if not hasattr(self, '_do'):
            self._do = DoManager(None, self.api_key, api_version=2)
        return self._do

    @property
    def droplets(self):
        if not hasattr(self, '_droplets'):
            self._droplets = self.do.all_active_droplets()
        return self._droplets

    def get_droplets(self):
        grp_prefix = "group"
        meta = self["_meta"] = {"hostvars": {}}

        for droplet in self.droplets:
            address = self.droplet_address(droplet)
            meta['hostvars'][address] = droplet
            name = droplet['name']
            n_split = name.split('.')
            node_type = self.get_node_type(name)
            if node_type:
                self.add_host(grp_prefix, node_type, address)
            for group in n_split:
                self.add_host(grp_prefix, group, address)
            self.add_host('name', name, address)
            self.add_host('image', droplet['image']['slug'], address)
            self.add_host('region', droplet['region']['slug'], address)
            self.add_host('size', droplet['size_slug'], address)

    def get_node_type(self, node):
        match = re.match('(\w+)-[0-9]+', node)
        if match.lastindex == 1:
            return match.group(1)
        return None

    def add_host(self, prefix, name, address):
        full_name = self.clean_name("{}_{}".format(prefix, name))
        if full_name not in self:
            self[full_name] = []

        self[full_name].append(address)

    def clean_name(self, name):
        return re.sub("[^A-Za-z0-9\-\.]", "_", name)

    def droplet_address(self, droplet):
        for v4 in droplet['networks']['v4']:
            if v4['type'] == self.address_type:
                return v4['ip_address']


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Ansible DigitalOcean inventory with filters')
    parser.add_argument('--apiv2-key', '-a', dest='apiv2_key', default=DEFAULT_API_KEY,
                        help='Digital Ocean apiv2 key')
    parser.add_argument('--filter-by-group', '-f', dest='filter_group', default=None,
                        action='append', help='filter inventory by group')

    args = parser.parse_args()
    inv = do_inv = DoInventory(args.apiv2_key)

    # NOTE: Example how to use filter on environment lib's
    if args.filter_group:
        for group in args.filter_group:
            inv = inv.filter_by("group_{}".format(group))

    print inv.dumps()
