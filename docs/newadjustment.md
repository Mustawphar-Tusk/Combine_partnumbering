Before proceeding to the next phase, please complete the following adjustments to the current implementation. Some elements have been added, but the quotation and customization workflow is not yet functioning as intended.

Inspect the current code and reuse existing services, tables, and metadata. Identify any missing backend capability explicitly rather than implementing a visual control that does not persist or complete its intended action.

### 1. Make draft quotes editable and resumable

A draft quote must be a working configuration that the distributor can reopen, edit, save, and complete.

When a distributor opens an item within a draft quote:

- Provide an **Edit Configuration** action that opens the configurator with that quote line’s saved selections, specifications, and customization requests.
- Allow the distributor to continue the build and change permitted selections.
- Save the changes back to the correct draft quote and line, rather than silently creating an unrelated quote or duplicate item.
- Recalculate configuration validity, specifications, PN/SKU, BOM, and pricing through the existing authoritative services.
- Preserve saved changes after navigation, refresh, and reopening.

Submitted or completed revisions must retain their history. Changes to those records must follow the established revision/review workflow rather than overwrite an accepted configuration.

### 2. Add multiple customization requests within each grouping

Each applicable pump configuration grouping must have a clearly visible **Custom** button.

Clicking it should open a modal asking what the distributor wants customized within that grouping. Allow the distributor to add more than one request using an **Add Another Customization** action.

Each request must retain:

- The affected grouping and field.
- The current value, where applicable.
- The requested change or specification.
- Supporting notes.

Allow requests to be edited or removed while the quote is a draft. Persist them against the correct quote line, grouping, and revision. They must remain visible when the quote is reopened and when engineering reviews it.

### 3. Submit incomplete or custom quotes to engineering

Provide a working **Submit to Engineering for Review** action after the distributor saves the configuration and customization requests.

Every unresolved **C/F** field must require engineering review, whether it represents missing pricing, a specification, or another required configuration value. Show a clear list of unresolved items; do not treat C/F as a completed value or an approved zero price.

Submission must persist the quote revision and requests, create the engineering queue entry, and notify the correct team:

| Brand | Responsible engineering team |
|---|---|
| Dean | Indianapolis — IND |
| Fybroc | Telford — TEL |

Enforce this routing and access restriction in the backend. Distributor or ship-to location must not change brand-based routing.

### 4. Allow engineering to resolve the configuration completely

The responsible application engineer must be able to open the submitted quote, review all requests, and edit the business fields necessary to complete it.

This includes:

- Entering missing C/F prices.
- Resolving custom configuration values and descriptions.
- Editing applicable seal, motor, and other grouping specifications.
- Recording the resolution of each customization request.
- Entering the required lead time.
- Revalidating dependent selections and recalculating the resulting configuration.

Specification changes must use the **existing governed custom-specification model in the database**. Where an approved custom field affects a grouping specification, resolve its custom specification/code through that model and regenerate the relevant PN segment through the authoritative numbering service.

Do not manually overwrite the final PN, concatenate arbitrary text into it, invent custom codes, or create a competing numbering implementation. Verify the current custom-spec tables and rules first. If a required mapping is missing, identify the gap and prevent finalization until it is resolved.

Retain the original and revised configuration, engineering changes, pricing basis, and reviewer identity.

### 5. Return the reviewed quote to the distributor

Engineering must not submit a completed review while required C/F values, specifications, prices, customization decisions, or lead time remain unresolved.

Once engineering submits its review:

- Return the exact reviewed revision to the owning distributor’s queue.
- Notify the distributor that it is ready.
- Display the completed configuration, custom specifications, PN/SKU, pricing, applicable loyalty discount, and lead time.
- Provide **Request Further Review** and **Confirm Order** actions.

A further-review request must return to the responsible brand/site engineering team with the distributor’s comments and revision history.

### 6. Complete the order and provide the same PDF to both parties

When the distributor selects **Confirm Order**, persist confirmation of the exact reviewed revision and make the completed record available to both parties.

The distributor must be able to generate/download its PDF. The associated application engineer must receive an order-completion notification and be able to generate/download the **same completed order document**.

Store the completed configuration, commercial terms, confirmation identity/time, and document reference. Later catalog, address, or discount changes must not alter that completed document.

Make confirmation and PDF generation retry-safe so repeated clicks do not create duplicate orders or documents. Show document-generation failures clearly and allow a controlled retry.

Here, **Confirm Order** means completing this CPQ workflow. Do not introduce D365 sales-order creation or other external order processing without a separately approved integration contract. Identify whether the existing quote number remains the document identifier or whether an additional CPQ order identifier is needed.

### 7. Match the earlier reference SPA’s configurator presentation

Reopen the earlier CPQ SPA reference I supplied and adopt its **pump configuration field-display style**, including its grouping, field arrangement, spacing, labels, and interaction patterns.

Do not merely retain the current field layout with different colors. Use the reference’s presentation while keeping the real API, SQL metadata, and engineering rules authoritative.

If the reference is unavailable, identify the missing file rather than guessing its appearance.

### Completion evidence required before advancing

Demonstrate this complete sequence:

**Reopen draft → edit configuration → add multiple customization requests → submit to the correct engineering queue → resolve C/F and custom specifications → regenerate PN and pricing → return for distributor review → confirm order → notify engineering → retrieve the same PDF.**

Also demonstrate that saved drafts remain editable after reopening, Dean/Fybroc queues remain isolated, and existing standard configuration/numbering behavior still passes regression checks.

Please report what already works, what needs changing, and any genuine schema or specification gaps. Update the implementation plan and complete these adjustments before declaring the workflow finished or advancing past its acceptance gate.