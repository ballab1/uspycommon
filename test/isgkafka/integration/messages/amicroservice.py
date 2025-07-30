################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################


class AService:
    def __init__(self, name, type):
        self.name = name
        self.type = type

    def print_name(self):
        print(f"Name: {self.name}")

    def set_name(self, name):
        self.name = name

    def get_name(self):
        return self.name

    def print_type(self):
        print(f"Type: {self.type}")
