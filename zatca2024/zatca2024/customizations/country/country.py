import frappe
import iso3166

def validate(doc, method=None):
    if doc.code:
        doc.code = code = doc.code.upper()
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