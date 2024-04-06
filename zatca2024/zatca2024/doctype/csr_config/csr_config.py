# Copyright (c) 2024, ERPGulf and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import delete_file_from_filesystem

class CSRConfig(Document):
	def on_update(self):
		csr_config = f"""csr.common.name={self.common_name}\ncsr.serial.number={self.serial_number}\ncsr.organization.identifier={self.organization_identifier}\ncsr.organization.unit.name={self.organization_unit_name}\ncsr.organization.name={self.organization_name}\ncsr.country.name={self.country_name}\ncsr.invoice.type={self.invoice_type}\ncsr.location.address={self.location_address}\ncsr.industry.business.category={self.industry_business_category}"""
		self.csr_config = csr_config
		with open(frappe.get_site_path()+"/sdkcsrconfig.properties",'w') as csr:
			csr.write(csr_config)
		
		# exists = frappe.db.exists("File",{"attached_to_doctype":self.doctype,"attached_to_name":self.name,"file_name":"sdkcsrconfig.properties"})

		# if not exists:
		# 	self.create_csr_config(csr_config)
		# else:
		# 	file = frappe.get_doc("File",exists)
		# 	delete_file_from_filesystem(file)
		self.create_csr_config(csr_config)
			
	def create_csr_config(self, content):
		file = frappe.get_doc({
				"doctype": "File",
				"file_name": "sdkcsrconfig.properties",
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"content": content 
				})

		file.save(ignore_permissions=True)