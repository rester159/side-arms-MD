#pragma once
#include "bc_rules.h"

/* Source text codes select independently rendered native caption glyphs. */
typedef struct {
    const unsigned char *bytes;
    unsigned short length;
} BcEndingCaption;
extern const BcEnemyData bc_gallery_data;
extern const unsigned short bc_gallery_bases[48];
extern const BcEndingCaption bc_gallery_captions[20];
extern const char * const bc_credit_rows[];
extern const unsigned short bc_credit_row_count;

extern const unsigned long bc_caption_tiles[1256];
extern const unsigned char bc_gallery_frame[41];
