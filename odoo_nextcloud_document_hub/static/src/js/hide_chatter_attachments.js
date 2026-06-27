/** @odoo-module **/

import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

const CHATTER_SELECTORS = [
    ".o_FormRenderer_chatterContainer",
    ".o-mail-Form-chatter",
    ".o-mail-Chatter",
    ".o-mail-ChatterTopbar",
    ".o_Chatter",
    ".o_chatter",
    ".o-mail-Thread",
    ".o-mail-AttachmentBox",
    ".o_AttachmentBox",
];

const ATTACH_BUTTON_SELECTORS = [
    "[data-hotkey='shift+a']",
    "[data-hotkey='a']",
    "[name='attach']",
    "[name='attachment']",
    "button[title*='Attach']",
    "button[title*='attach']",
    "button[title*='Dosya']",
    "button[title*='Ek']",
    "button[aria-label*='Attach']",
    "button[aria-label*='attach']",
    "button[aria-label*='Dosya']",
    "button[aria-label*='Ek']",
    ".o-mail-ChatterTopbar-attachments",
    ".o-mail-Chatter-attachFiles",
    ".o-mail-Composer-attachFiles",
    ".o-mail-Composer button",
    ".o_AttachmentBox_buttonAdd",
    ".o-mail-AttachmentBox button",
];

function isAttachText(text) {
    const value = (text || "").trim().toLowerCase();
    return [
        "attach files",
        "attach file",
        "add files",
        "add file",
        "dosya ekle",
        "dosya ekleyin",
        "dosya yükle",
        "ek dosya",
        "ekle",
    ].some((label) => value.includes(label));
}

function hideElement(element) {
    element.classList.add("d-none");
    element.classList.add("o_nextcloud_hide_chatter_attachment");
    element.setAttribute("aria-hidden", "true");
    element.setAttribute("tabindex", "-1");
}

function hideChatterAttachments() {
    for (const chatterSelector of CHATTER_SELECTORS) {
        for (const chatter of document.querySelectorAll(chatterSelector)) {
            for (const selector of ATTACH_BUTTON_SELECTORS) {
                for (const button of chatter.querySelectorAll(selector)) {
                    if (
                        button.matches(".o-mail-Composer button")
                        && !button.querySelector(".fa-paperclip")
                        && !isAttachText(button.textContent)
                    ) {
                        continue;
                    }
                    hideElement(button);
                }
            }
            for (const icon of chatter.querySelectorAll(".fa-paperclip")) {
                const target = icon.closest("button, a, label, .btn") || icon;
                hideElement(target);
            }
            for (const button of chatter.querySelectorAll("button")) {
                if (isAttachText(button.textContent)) {
                    hideElement(button);
                }
            }
            for (const input of chatter.querySelectorAll("input[type='file']")) {
                hideElement(input);
            }
        }
    }
}

function isInChatter(target) {
    return CHATTER_SELECTORS.some((selector) => target.closest(selector));
}

function blockChatterFileDrop(event) {
    if (
        event.dataTransfer?.files?.length
        && event.target instanceof Element
        && isInChatter(event.target)
    ) {
        event.preventDefault();
        event.stopPropagation();
    }
}

registry.category("services").add("nextcloud_hide_chatter_attachments", {
    async start() {
        if (await user.hasGroup("base.group_system")) {
            return;
        }
        document.body.classList.add("o_nextcloud_no_native_attachment");
        hideChatterAttachments();
        const observer = new MutationObserver(hideChatterAttachments);
        observer.observe(document.body, { childList: true, subtree: true });
        document.addEventListener("drop", blockChatterFileDrop, true);
        document.addEventListener("dragover", blockChatterFileDrop, true);
    },
});
