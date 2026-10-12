#include "bc_stage.h"

void bc_stage_checkpoint_initial(BcStage *s, const unsigned char header[8])
{
    s->checkpoint_x = header[0];
    s->checkpoint_y = header[1];
    s->checkpoint_script = header[6] | ((unsigned short)header[7] << 8);
}

void bc_stage_checkpoint_restore(BcStage *s, const unsigned char header[8])
{
    s->terrain_attributes = header[4] | ((unsigned short)header[5] << 8);
    s->x = (unsigned int)s->checkpoint_x << 16;
    s->y = (unsigned int)s->checkpoint_y << 16;
    s->script = s->checkpoint_script;
}

void bc_stage_scroll(BcStage *s)
{
    s->x = (s->x + s->dx) & 0x0fffff;
    s->y = (s->y + s->dy) & 0x0fffff;
}

unsigned short bc_stage_event_next(BcStage *s, const BcEnemyData *data)
{
    const unsigned char *event = data->bytes + (unsigned short)(s->script - data->origin);
    unsigned char position = (s->dy ? s->y : s->x) >> 8;
    if (event[0] != position) return 0;
    if (position == 255) {
        if (event[1] == 255) return 0;
        if (event[1] == 254) { s->script += 2; return 0; }
    }
    return event[1] | ((unsigned short)event[2] << 8);
}

void bc_stage_event_complete(BcStage *s)
{
    s->script += 3;
}

unsigned char bc_stage_control(BcStage *s, unsigned short handler)
{
    switch (handler) {
    case 0x8be9: s->dx = 85; return 1;
    case 0x8bf2: s->dx = -85; return 1;
    case 0x8bfb: s->dx = 0; return 1;
    case 0x8c00: s->dy = 85; return 1;
    case 0x8c09: s->dy = -85; return 1;
    case 0x8c12: s->dy = 0; return 1;
    case 0x8c17: s->stopped = 1; return 1;
    case 0x8c1c: s->shot_limit = 0; return 1;
    case 0x8c1f: s->shot_limit = 1; return 1;
    case 0x8c23: s->shot_limit = 2; return 1;
    case 0x8c27: s->shot_limit = 3; return 1;
    case 0x8c2b: s->shot_limit = 4; return 1;
    case 0x8c2f: s->shot_limit = 5; return 1;
    case 0x8c33: s->shot_limit = 6; return 1;
    case 0x8c37: s->shot_limit = 7; return 1;
    case 0x8c3b: s->shot_limit = 8; return 1;
    case 0x8c3f: s->shot_limit = 10; return 1;
    case 0x8c43: s->shot_limit = 12; return 1;
    case 0x8c47: s->shot_limit = 14; return 1;
    case 0x8c4b: s->shot_limit = 16; return 1;
    default: return 0;
    }
}
