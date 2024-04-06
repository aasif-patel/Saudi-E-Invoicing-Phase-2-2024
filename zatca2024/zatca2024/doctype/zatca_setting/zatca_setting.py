# Copyright (c) 2024, ERPGulf and contributors
# For license information, please see license.txt

import frappe
import json
import os
from frappe.model.document import Document
from zatca2024.zatca2024.customizations.zatca.file_manager import update_sdk_config

class Zatcasetting(Document):
	def validate(self):
		if self.sdk_root and not os.path.exists(self.sdk_root+"/Apps"):
			frappe.throw("SDK Root is not valid.")

	def before_save(self):
		self.sdk_root = self.sdk_root.removesuffix('/')
		old_doc = self.get_doc_before_save()

		if old_doc and old_doc.sdk_root != self.sdk_root and self.sdk_root:
			update_sdk_config(self.sdk_root)

