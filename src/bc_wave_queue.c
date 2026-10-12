#include "bc_wave.h"

unsigned char bc_wave_enqueue(BcWaveQueue *q, unsigned char players,
    unsigned short script, unsigned char size)
{
    if (q->count == BC_WAVE_QUEUE_CAPACITY) return 0;
    unsigned char copies = bc_wave_copies(&q->scale, players, size);
    if (!copies) return 1;
    q->originals += size;
    if (--copies) {
        unsigned char tail = (q->head + q->count) & (BC_WAVE_QUEUE_CAPACITY-1);
        q->pending[tail] = (BcPendingWave){script, size, copies};
        if (!q->count) q->delay = BC_WAVE_SPACING;
        q->count++;
    }
    return 1;
}

void bc_wave_service(BcWaveQueue *q, BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player,
    const BcStageEventData *data, unsigned char *limited_count)
{
    if (!q->count || (q->delay && --q->delay)) return;
    BcPendingWave *wave = &q->pending[q->head];
    BcStageEventResult result = bc_runtime_stage_replay(stage, actors, player,
        data, limited_count, wave->script);
    if (result.status != 1 || result.slot < 0) { q->blocked++; return; }
    q->extras += wave->size;
    if (!--wave->copies) {
        q->head = (q->head + 1) & (BC_WAVE_QUEUE_CAPACITY-1);
        q->count--;
    }
    q->delay = BC_WAVE_SPACING;
}

unsigned char bc_wave_barrier(unsigned char round, unsigned short handler,
    signed short relocation)
{
    unsigned short canonical = handler - relocation;
    if (canonical == 0x8d76 || canonical == 0x8c17) return 1;
    switch (round) {
    case 0: return handler == 0xb34b;
    case 1: return handler == 0xab95;
    case 2: return handler == 0xaacb;
    case 3: return handler == 0xa76e;
    case 4: return handler == 0xac50;
    case 5: return handler == 0xae4c;
    case 6: return handler == 0xaa0b;
    case 7: return handler == 0xb046;
    case 8: return handler == 0xa574 || handler == 0xb384 || handler == 0xaff2 ||
        handler == 0xac32 || handler == 0xc18b || handler == 0xa8c6 ||
        handler == 0xb8d4 || handler == 0xbcf0 || handler == 0xc539;
    case 9: return handler == 0xa399;
    default: return 0;
    }
}
