/** @odoo-module **/

import { prettifyMessageContent } from "@mail/utils/common/format" ;

import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

/** @type {import("@mail/core/common/thread_service").Thread} */
const threadServicePatch1 = {
    
    async getMessagePostParams({attachments, body, cannedResponseIds, isNote, rawMentions, thread,}) {

        const subtype = isNote ? "mail.mt_note" : "mail.mt_comment";
        const validMentions = this.store.user
            ? this.messageService.getMentionsFromText(rawMentions, body)
            : undefined;
        const partner_ids = validMentions?.partners.map((partner) => partner.id);
        let recipientEmails = [];
        if (!isNote) {
            const recipientIds = thread.suggestedRecipients
                .filter((recipient) => recipient.persona && recipient.checked)
                .map((recipient) => recipient.persona.id);
            recipientEmails = thread.suggestedRecipients
                .filter((recipient) => recipient.checked && !recipient.persona)
                .map((recipient) => recipient.email);
            partner_ids?.push(...recipientIds);
        }
        // console.log('validMentions',validMentions)
        return {
            context: {
                mail_post_autofollow: !isNote && thread.hasWriteAccess,
            },
            post_data: {
                body: await prettifyMessageContent(body, []),
                attachment_ids: attachments.map(({ id }) => id),
                attachment_tokens: attachments.map((attachment) => attachment.accessToken),
                canned_response_ids: cannedResponseIds,
                message_type: "comment",
                partner_ids,
                subtype_xmlid: subtype,
                partner_emails: recipientEmails,
            },
            thread_id: thread.id,
            thread_model: thread.model,
        };
            
    
    },
};

patch(Thread.prototype, threadServicePatch1);
