# Copyright (c) 2024, ERPGulf and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class CSRConfig(Document):
	def before_save(self):
		csr_config = f"""csr.common.name={self.common_name}\ncsr.serial.number={self.serial_number}\ncsr.organization.identifier={self.organization_identifier}\ncsr.organization.unit.name={self.organization_unit_name}\ncsr.organization.name={self.organization_name}\ncsr.country.name={self.country_name}\ncsr.invoice.type={self.invoice_type}\ncsr.location.address={self.location_address}\ncsr.industry.business.category={self.industry_business_category}"""
		
		with open("sdkcsrconfig.properties",'w') as csr:
			csr.write(csr_config)
		
		file = frappe.get_doc({
				"doctype": "File",
				"file_name": f"sdkcsrconfig.properties.csr",
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"content": csr_config 
				})

		file.save(ignore_permissions=True)