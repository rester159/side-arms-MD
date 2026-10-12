#include "bc_boss_art.h"
#include "bg.h"
#include "sprites.h"
#include "gen/assets.h"
#include "gen/bc_boss_meta.h"

extern const u8 bc_boss_patterns[] __attribute__((weak));
extern const u8 bc_boss2_patterns[] __attribute__((weak));
extern const u8 bc_boss3_patterns[] __attribute__((weak));
extern const u8 bc_boss4_patterns[] __attribute__((weak));
extern const u8 bc_boss9_patterns[] __attribute__((weak));
extern const u8 bc_boss8_patterns[] __attribute__((weak));
extern const u8 bc_boss7_patterns[] __attribute__((weak));
extern const u8 bc_boss6_patterns[] __attribute__((weak));
extern const u8 bc_boss5_patterns[] __attribute__((weak));
static u16 tiles[BC_BOSS_BLOCK_CAPACITY];
static u8 loaded_round;
static u8 ready;
static s16 source_shift;

static const u8 *boss_patterns(u8 round)
{
    return round == 8 ? bc_boss9_patterns : round == 7 ? bc_boss8_patterns : round == 6 ? bc_boss7_patterns : round == 5 ? bc_boss6_patterns : round == 4 ? bc_boss5_patterns : round == 3 ? bc_boss4_patterns : round == 2 ? bc_boss3_patterns : round == 1 ? bc_boss2_patterns : bc_boss_patterns;
}

static void init_round(unsigned char round, unsigned char sequence)
{
    const u8 *patterns = boss_patterns(round);
    loaded_round = round;
    source_shift = 0;
    ready = 0;
    if (round > 8 || !patterns) return;
    u16 body_count = bc_boss_banks[round].blocks;
    u16 count = sequence ? BC_BOSS_BLOCK_CAPACITY : body_count;
    u16 got = bg_reserve_blocks(count, tiles);
    if (got != count) { bg_release_blocks(); return; }
    /* Called while display is disabled; keep boss blocks resident throughout
     * the scene, including checkpoint resets. No per-frame pattern upload. */
    for (u16 i = 0; i < body_count; i++)
        DMA_doDma(DMA_VRAM, (void *)(patterns + i * 512), tiles[i] * 32, 256, 2);
    ready = 1;
}

void bc_boss_art_init_round(unsigned char round) { init_round(round, 0); }

void bc_boss_art_init_sequence(void)
{
    /* Reserve the largest complete original body/attack bank once. */
    init_round(4, 1);
}

void bc_boss_art_queue_encounter(unsigned char encounter)
{
    static const s16 shifts[9] = {-0xdd7, 0x7ef, 0x527, 0x4c4, 0x153b, -0x586, 0xec9, 0xcaa, 0};
    if (!ready || encounter >= 9) return;
    const u8 *patterns = boss_patterns(encounter);
    u16 body_count = bc_boss_banks[encounter].blocks;
    for (u16 i = 0; i < body_count; i++)
        DMA_queueDma(DMA_VRAM, (void *)(patterns + i * 512), tiles[i] * 32, 256, 2);
    loaded_round = encounter; source_shift = shifts[encounter];
}

void bc_boss_art_init_encounter(unsigned char encounter, unsigned char source_round)
{
    static const s16 shifts[9] = {-0xdd7, 0x7ef, 0x527, 0x4c4, 0x153b, -0x586, 0xec9, 0xcaa, 0};
    bc_boss_art_init_round(encounter);
    if (source_round == 8 && encounter < 9) source_shift = shifts[encounter];
}

void bc_boss_art_init(void) { bc_boss_art_init_round(0); }

unsigned char bc_boss_draw(const BcActor *a, signed short ox, signed short oy)
{
    u16 frame = a->body.sprite;
    if (frame > 255) frame -= source_shift;
    if (!(a->body.flags & 8)) return 0;
    s16 x = (s16)bc_enemy_x(&a->body) + ox;
    s16 y = (s16)bc_enemy_y(&a->body) + oy;
    if (!ready || loaded_round >= 9) return 0;
    const BcBossBank *bank = &bc_boss_banks[loaded_round];
    for (u16 i = 0; i < bank->pose_count; i++) {
        const BcBossPose *pose = &bank->poses[i];
        if (pose->family != a->sprite_base_ref) continue;
        if (!a->body.state || !frame || frame == 255) return 1;
        if (pose->frame != frame) continue;
        for (u16 j = 0; j < pose->count; j++) {
            const BcBossPiece *piece = &bank->pieces[pose->first+j];
            spr_tile32_flags(tiles[piece->tile], pose->palette, x + piece->x, y + piece->y, piece->flags);
        }
        return 1;
    }
    return 0;
}
