# Mentality DB - Changelog v0.20.2 (March 18, 2026)

## Search Fixes

- Basic search now covers all card fields: first/last name RU, first/last name EN, country, city, address, and phone number.
- Phone number search normalization has been added: searching by digits works even if the phone number contains spaces, brackets, hyphens, and the '+' sign.
- Advanced search has been fixed for address and phone number: values ​​are correctly converted to text and compared without type errors.
- After an advanced search, the list is actually filtered by found cards and highlighted.

## Card Creation Fixes

- New cards are no longer saved to the database until the save button is clicked.
- If you exit a card without saving, the empty card does not appear in the list.

## Interface Theme

- Emptying the trash bin and selecting the export mode again work through the themed app dialogs. - Fixed custom dialog creation: the 'grab failed: window not viewable' exception has been resolved.

## Archiving

- Previous versions of the 'README', 'CHANGELOG', and script snapshot have been saved to 'old_data'.
