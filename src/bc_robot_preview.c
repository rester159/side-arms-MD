#include "hud.h"
#include "game.h"
#include "sprites.h"
#include "bc_robot_art.h"
#include "bc_projectile_art.h"
#include "bc_actor_art.h"
#include "bc_boss_art.h"
#include "bg.h"
#include "bc_background.h"

/* Emulator-driven artwork inspection only. Not a Before Christ game mode.
 * Inputs: state, center X/Y, source body frame, source attributes per robot. */
volatile u16 dbg_bc_robot_preview;
volatile u16 dbg_bc_boss_source_round; /* One-based source round; zero uses original. */
volatile u16 dbg_bc_boss_preview; /* One-based round; set before opening. */
volatile u16 dbg_bc_robot_pose[4][5];
volatile BcRobotArt dbg_bc_robot_art;
volatile u16 dbg_bc_robot_unmapped;
/* Projectile inputs: source frame, center X/Y, attributes, facing. Zero hides. */
volatile u16 dbg_bc_projectile_pose[16][5];
volatile u16 dbg_bc_projectile_unmapped;
/* Enemy inputs: base reference, resolved base, frame, attributes, X/Y, state. */
volatile u16 dbg_bc_actor_pose[16][7];
volatile u16 dbg_bc_actor_unmapped;
/* Optional stage-map inspection. Pointers refer to immutable ROM data. */
volatile u16 dbg_bc_background;
volatile u16 dbg_bc_camera[2];
volatile u32 dbg_bc_cells;
volatile u16 dbg_bc_remap[256];
extern const Zone bc_bg_draft __attribute__((weak));
extern const u16 bc_bg_remap[] __attribute__((weak));
extern const Zone bc_bg10_draft __attribute__((weak));
extern const u16 bc_bg10_remap[] __attribute__((weak));
extern const Zone bc_bg9_draft __attribute__((weak));
extern const u16 bc_bg9_remap[] __attribute__((weak));
extern const Zone bc_bg8_draft __attribute__((weak));
extern const u16 bc_bg8_remap[] __attribute__((weak));
extern const Zone bc_bg7_draft __attribute__((weak));
extern const u16 bc_bg7_remap[] __attribute__((weak));
extern const Zone bc_bg6_draft __attribute__((weak));
extern const u16 bc_bg6_remap[] __attribute__((weak));
extern const Zone bc_bg5_draft __attribute__((weak));
extern const u16 bc_bg5_remap[] __attribute__((weak));
extern const Zone bc_bg4_draft __attribute__((weak));
extern const u16 bc_bg4_remap[] __attribute__((weak));
extern const Zone bc_bg3_draft __attribute__((weak));
extern const u16 bc_bg3_remap[] __attribute__((weak));
extern const Zone bc_bg2_draft __attribute__((weak));
extern const u16 bc_bg2_remap[] __attribute__((weak));

bool bc_robot_preview_frame(void)
{
    static bool active;
    if (!dbg_bc_robot_preview) {
        if (active) { active = FALSE; bg_release_blocks(); video_init(); game_init(); }
        return FALSE;
    }
    if (!active) {
        active = TRUE;
        hud_suspend();
        SYS_setVBlankCallback(NULL);
        VDP_setEnable(FALSE);
        VDP_setWindowVPos(FALSE, 0);
        VDP_setScrollingMode(HSCROLL_PLANE, VSCROLL_PLANE);
        VDP_clearPlane(BG_A, TRUE); VDP_clearPlane(BG_B, TRUE); VDP_clearPlane(WINDOW, TRUE);
        VDP_setHorizontalScroll(BG_A, 0); VDP_setHorizontalScroll(BG_B, 0);
        VDP_setVerticalScroll(BG_A, 0); VDP_setVerticalScroll(BG_B, 0);
        PAL_setColor(0, 0); spr_init();
        if (dbg_bc_background) {
            if (dbg_bc_background == 11 && &bc_bg10_draft && bc_bg10_remap)
                bg_set_stage(&bc_bg10_draft, (const u8 *)dbg_bc_cells, bc_bg10_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 10 && &bc_bg9_draft && bc_bg9_remap)
                bg_set_stage(&bc_bg9_draft, (const u8 *)dbg_bc_cells, bc_bg9_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 9 && &bc_bg8_draft && bc_bg8_remap)
                bg_set_stage(&bc_bg8_draft, (const u8 *)dbg_bc_cells, bc_bg8_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 8 && &bc_bg7_draft && bc_bg7_remap)
                bg_set_stage(&bc_bg7_draft, (const u8 *)dbg_bc_cells, bc_bg7_remap, bc_bg_sources, 16);
            else if (dbg_bc_background == 7 && &bc_bg6_draft && bc_bg6_remap)
                bg_set_stage(&bc_bg6_draft, (const u8 *)dbg_bc_cells, bc_bg6_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 6 && &bc_bg5_draft && bc_bg5_remap)
                bg_set_stage(&bc_bg5_draft, (const u8 *)dbg_bc_cells, bc_bg5_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 5 && &bc_bg4_draft && bc_bg4_remap)
                bg_set_stage(&bc_bg4_draft, (const u8 *)dbg_bc_cells, bc_bg4_remap, bc_bg_sources, 16);
            else if (dbg_bc_background == 4 && &bc_bg3_draft && bc_bg3_remap)
                bg_set_stage(&bc_bg3_draft, (const u8 *)dbg_bc_cells, bc_bg3_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 3 && &bc_bg2_draft && bc_bg2_remap)
                bg_set_stage(&bc_bg2_draft, (const u8 *)dbg_bc_cells, bc_bg2_remap, bc_bg_sources, 0);
            else if (dbg_bc_background == 2 && &bc_bg_draft && bc_bg_remap)
                bg_set_stage(&bc_bg_draft, (const u8 *)dbg_bc_cells, bc_bg_remap, bc_bg_sources, 0);
            else
                bg_set_stage(&zones[0], (const u8 *)dbg_bc_cells, (const u16 *)dbg_bc_remap, NULL, 0);
            bg_enable(TRUE);
        }
        if (dbg_bc_boss_preview) bc_boss_art_init_encounter(dbg_bc_boss_preview - 1,
            dbg_bc_boss_source_round ? dbg_bc_boss_source_round - 1 : dbg_bc_boss_preview - 1);
        VDP_setEnable(TRUE);
    }
    if (dbg_bc_background) {
        bg_set_camera(dbg_bc_camera[0], dbg_bc_camera[1]);
        bg_update();
    }
    BcRobotArt art;
    for (u16 i = 0; i < 9; i++) {
        art.source[i] = dbg_bc_robot_art.source[i];
        art.genesis[i] = dbg_bc_robot_art.genesis[i];
    }
    spr_bc_begin();
    dbg_bc_robot_unmapped = 0;
    for (u16 i = 0; i < 4; i++) {
        BcPlayerControl p;
        p.world.state = dbg_bc_robot_pose[i][0];
        p.world.x = (u32)dbg_bc_robot_pose[i][1] << 8;
        p.world.y = (u32)dbg_bc_robot_pose[i][2] << 8;
        p.body_frame = dbg_bc_robot_pose[i][3];
        p.attributes = dbg_bc_robot_pose[i][4];
        if (!bc_robot_draw(&art, &p, i, 32, 0, 0)) dbg_bc_robot_unmapped++;
    }
    dbg_bc_projectile_unmapped = 0;
    for (u16 i = 0; i < 16; i++) {
        BcBeam b = {0};
        b.sprite = dbg_bc_projectile_pose[i][0];
        if (!b.sprite) continue;
        b.state = 128;
        bc_beam_set_x(&b, dbg_bc_projectile_pose[i][1]);
        bc_beam_set_y(&b, dbg_bc_projectile_pose[i][2]);
        b.attributes = dbg_bc_projectile_pose[i][3];
        b.facing = dbg_bc_projectile_pose[i][4];
        BcProjectileSprite s = bc_projectile_sprite(&b, 32, 0);
        if (s.visible) spr_16(s.code, s.colour, s.x, s.y, s.flips);
        else if (!s.handled) dbg_bc_projectile_unmapped++;
    }
    dbg_bc_actor_unmapped = 0;
    for (u16 i = 0; i < 16; i++) {
        BcActor a = {0};
        a.body.state = dbg_bc_actor_pose[i][6];
        if (!a.body.state) continue;
        a.sprite_base_ref = dbg_bc_actor_pose[i][0];
        a.body.sprite_base = dbg_bc_actor_pose[i][1];
        a.body.sprite = dbg_bc_actor_pose[i][2];
        a.body.attributes = dbg_bc_actor_pose[i][3];
        bc_enemy_set_x(&a.body, dbg_bc_actor_pose[i][4]);
        bc_enemy_set_y(&a.body, dbg_bc_actor_pose[i][5]);
        if (dbg_bc_boss_preview && (a.sprite_base_ref == 0x36b6 || a.sprite_base_ref == 0x36c4 || a.sprite_base_ref == 0x36bc || a.sprite_base_ref == 0x36be || a.sprite_base_ref == 0x36b8 || a.sprite_base_ref == 0x36ba || a.sprite_base_ref == 0x36c6 || a.sprite_base_ref == 0x36c0 || a.sprite_base_ref == 0x36c2 || a.sprite_base_ref == 0x36ca ||
            (a.sprite_base_ref == 0x36c8 && (a.body.sprite == 0xab1d || a.body.sprite == 0xafe1)))) {
            a.body.flags = 8;
            if (!bc_boss_draw(&a, 32, 0)) dbg_bc_actor_unmapped++;
            continue;
        }
        BcActorSprite s = dbg_bc_boss_preview ? bc_actor_boss_sprite(&a, 32, 0) : bc_actor_sprite(&a, 32, 0);
        if (!s.handled) dbg_bc_actor_unmapped++;
        if (s.visible) {
            if (s.size == 32) spr_32(s.code, s.colour, s.x, s.y, s.flips);
            else spr_16(s.code, s.colour, s.x, s.y, s.flips);
        }
    }
    spr_end();
    return TRUE;
}
