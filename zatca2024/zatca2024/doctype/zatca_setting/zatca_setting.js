// Copyright (c) 2024, ERPGulf and contributors
// For license information, please see license.txt

frappe.ui.form.on("Zatca setting", {
	refresh(frm) {
        if(frm.doc.sdk_root){
            frm.add_custom_button(__("Update SDK Config"), function() {
                frm.call({
                    method:"zatca2024.zatca2024.customizations.zatca.file_manager.update_sdk_config",
                    args: {
                        "sdk_root": cur_frm.doc.sdk_root
                    },
                });
            })
        }
       
    },
    production_csid: function (frm) {
        frappe.call({
            method: "zatca2024.zatca2024.customizations.zatca.zatcasdkcode.production_CSID",
            args: {
              
            },
            callback: function (r) {
                if (!r.exc) {
                    frm.save();
                    window.open(r.message.url);
                }
            },
        });
    },
    csid_attach: function (frm) {
            frappe.call({
                method: "zatca2024.zatca2024.customizations.zatca.zatcasdkcode.create_CSID",
                args: {
                  
                },
                callback: function (r) {
                    if (!r.exc) {
                        frm.save();
                        window.open(r.message.url);
                    }
                },
            });
        },
    create_csr: function (frm) {
        frappe.call({
            method: "zatca2024.zatca2024.customizations.zatca.zatcasdkcode.generate_csr",
            args: {
              
            },
            callback: function (r) {
                if (!r.exc) {
                    frm.save();
                    window.open(r.message.url);
                }
            },
        });
    },
    check_compliance: function (frm) {
         
            frappe.call({
            method: "zatca2024.zatca2024.customizations.zatca.zatcasdkcode.zatca_Call_compliance",
            args: {
                "invoice_number": frm.doc.sample_invoice_to_test,
            },
            callback: function (r) {
                if (!r.exc) {
                    // frm.save();                  
                }
            },
            
        });
    }
    
});


