import frappe
import iso3166
from frappe import _

def validate(doc, method=None):
    if doc.code:
        doc.code = code = doc.code.upper()
        country = iso3166.countries_by_alpha2.get(code)
        if not country:
               frappe.throw(_("Country code is not correct, remove it to autofetch."))
        if country.name != doc.country_name:
               frappe.throw(_("As per the code country name should be <b>{0}</b>.").format(country.name))
    else:
        country = iso3166.countries_by_name.get(doc.country_name.upper())
        if not country:
               frappe.throw(_("Country name '<b>{0}</b>' might not correct.").format(doc.country_name))
        doc.code = country.alpha2