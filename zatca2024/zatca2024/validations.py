import frappe
import iso3166

def zatca_done_or_not(doc, method=None):
        if doc.custom_zatca_status != "REPORTED" and doc.custom_zatca_status != "CLEARED":
                frappe.throw("Please send this invoice to ZATCA, before submitting")
                
def before_save(doc, method=None):
        if doc.custom_zatca_status in ("REPORTED", "CLEARED"):
                frappe.throw("This invoice is already submitted to ZATCA. You cannot edit, cancel or save it.")

def duplicating_invoice(doc, method=None):
            # required on version 13  as no-copy settings on fields not available
            # frappe.msgprint(frappe.__version__)
            # frappe.msgprint(int(frappe.__version__.split('.')[0]))
            if int(frappe.__version__.split('.')[0]) == 13:
                    frappe.msgprint("duplicating invoice")
                    doc.custom_uuid = "Not submitted"
                    doc.custom_zatca_status = "Not Submitted"
                    doc.save()

def test_save_validate(doc, method=None):
        # frappe.msgprint("test save validate")
        frappe.msgprint("test save validated and stopped it here")

#Doctype Country to validate country code for Zatca
def validate_country_code(doc, method=None):
    if doc.code:
        code = doc.code.upper()
        country = iso3166.countries_by_alpha2.get(code)
        if not country:
               frappe.throw("Country code is not correct, remove it to autofetch.")
        if country.name != doc.country_name:
               frappe.throw(f"As per the code country name should be <b>{country.name}</b>.")
    else:
        country = iso3166.countries_by_name.get(doc.country_name.upper())
        if not country:
               frappe.throw("Country name '<b>{doc.country_name}</b>' might not correct.")

        doc.code = country.alpha2