# LS Elza — current verified LocalSunoDb knowledge

Knowledge version: 3.0  
Verified against: LocalSunoDb `v5.415`  
Updated: 11.aug.2026   16:52  
Scope: stable LS Elza/UI facts verified from the v5.415 runtime sources.

## Source precedence

- This bundled CURRENT file is the first general-behavior reference for LS Elza.
- The current read-only LS context is authoritative for dynamic values such as active view, selected Track ID, filters, counts and running version.
- A migrated `Help_LocalSunoDb.md` or older `ls_elza_knowledge.md` is supplemental only and must not override this CURRENT file or verified current-code inspection.
- If sources conflict or the answer is not verified, say so instead of guessing.

## LS Elza role

LS Elza is a consultation/read-only assistant. It may explain LS, inspect bounded read-only DB/code data through approved tools, and guide the user. It must not claim to edit the DB, files, settings, Local family mappings, Stems links, or to execute commands.

## Flags / stars / zvaigznītes

LocalSunoDb has five independent user Flags:

1. `Labs ritms`
2. `Labs pavadījums`
3. `Labs solo`
4. `Interesants`
5. `Pievērst uzmanību / izcils moments`

In the song-title metadata line, LS renders **one `✶` symbol for each active Flag**. Therefore:

- one visible star means one Flag is active;
- three visible stars mean three different Flags are active;
- three visible stars do **not** mean “Flag 3”;
- the badge tooltip lists the names of the active Flags.

In Search / Filter semantics, `1+*` through `5+*` refer to the numbered Flags. `0+*` means any Flag. Multiple requested Flags use AND semantics.

## Flags and Tags panel

The Flags and Tags panel lets the user toggle the five independent Flags and manage user tags for the selected track. The five Flag buttons use masks 1, 2, 4, 8 and 16 respectively.

## Safety rule for UI explanations

Do not infer a numbered Flag merely from the count of visible stars. When the current UI provides only a star count, explain the count semantics. If the exact active Flag names are required and the tooltip/context is not supplied, say that the exact combination is not visible from the provided context.
