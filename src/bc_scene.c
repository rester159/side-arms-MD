#include "bc_hud.h"
#include "enemy_storage.h"
#include "enemies.h"
#include "boss.h"
#include "flow.h"
#include "game_session.h"
#include "level_storage.h"
#include "bc_party.h"
#include "bc_actor_audio.h"
#include "sound.h"
#include "hud.h"
#include "game.h"
#include "sprites.h"
#include "bc_runtime.h"
#include "bc_robot_art.h"
#include "bc_projectile_art.h"
#include "bc_actor_art.h"
#include "bc_boss_art.h"
#include "bg.h"
#include "bc_background.h"
#include "bc_round_exit.h"
#include "bc_round_data.h"
#include "bc_gallery.h"
#include "bc_ending_data.h"
#include "bc_continue.h"
#include "gen/player_data.h"
#include "gen/assets.h"
#include "palette.h"

/* Native development scene: all ten rounds and co-op controllers. Draft art,
 * co-op encounter scaling, final presentation and speed still need completion. */
static const BcRoundResource *resource;
static u8 ending_bonus_phase;
static u16 ending_bonus_clock, ending_bonus_units[4];
static u8 ending_robots[4];
static BcGallery ending_gallery;
static u8 ending_gallery_limited;
static u16 ending_credit_clock, ending_music_clock;
static u8 home_extend_thresholds[6][8], home_extend_count;
static BcContinue continue_prompts[4];
static u8 unused_continues[4], continue_pending, continue_shown;
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
volatile u16 dbg_bc_native_background_off, dbg_bc_native_background_active;
volatile u16 dbg_bc_native, dbg_bc_native_audio_ack, dbg_bc_native_protect;
volatile u16 dbg_bc_native_start_round, dbg_bc_native_current_round;
volatile u16 dbg_bc_native_hold_exit;
volatile u16 dbg_bc_native_status, dbg_bc_native_handler, dbg_bc_native_actors;
volatile u16 dbg_bc_native_camera[2], dbg_bc_native_position[2], dbg_bc_native_unmapped;
volatile u32 dbg_bc_native_ticks, dbg_bc_native_events;
volatile u16 dbg_bc_native_profile[3]; /* score/defeat, simulation, draw; SGDK subticks */
volatile u16 dbg_bc_native_profile_on;
volatile u16 dbg_bc_native_draw_profile[4]; /* background, player, actors, HUD */
volatile u16 dbg_bc_native_actor_unmapped;
volatile u16 dbg_bc_native_die, dbg_bc_native_lives, dbg_bc_native_resets;
volatile u16 dbg_bc_native_audio_manual, dbg_bc_native_music_command, dbg_bc_native_music_requests;
volatile u16 dbg_bc_native_sfx_commands, dbg_bc_native_sfx_dropped;
volatile u32 dbg_bc_native_sfx_mask;
volatile u16 dbg_bc_native_actor_sfx_commands, dbg_bc_native_actor_sfx_dropped;
volatile u32 dbg_bc_native_actor_sfx_mask;
static BcActorAudio actor_audio;

static u32 profile_clock(void)
{
    return getSubTick();
}

#define player (player_arena.bc)
static BcScore peer_scores[3];
static BcPartyControl party_control;
static u8 party_count;
volatile u16 dbg_bc_native_players, dbg_bc_native_die_mask;
volatile u16 dbg_bc_native_party_position[4][2], dbg_bc_native_party_lives[4];
volatile u16 dbg_bc_native_party_respawns[4];
static BcPlayerControl *member(u8 i) { return i ? &peers[i-1] : &player; }

#define actors (enemy_arena.bc)
#define stage level_bc
static BcScore score;
static BcPalette palette;
static BcAudioRequest audio_request;
static u8 startup_audio;
static bool terminal_shown;
static BcRoundExit round_exit;
volatile u16 dbg_bc_native_round_exit;
volatile u16 dbg_bc_native_boss_defeat;
volatile u16 dbg_bc_native_encounter;
static BcDefeatSequence defeat;
static BcFrameCursor cursor;
static BcStageEventData stage_data;
static BcActorStepData actor_data;
static BcRuntimeEvents events;
static BcRobotArt art;
static u16 seed;
static u8 limited_count, scheduler_counter;

static u16 word(u16 address)
{
    const u8 *p = resource->data.bytes + (u16)(address - 0x4000);
    return p[0] | ((u16)p[1] << 8);
}

static u16 base(u16 reference)
{
    const u8 *p = resource->sprite_bases + reference - 0x367a;
    return ((u16)p[0] << 8) | p[1];
}

static u16 template_base(u16 address) { return base(word(address + 11)); }

static u8 buttons(u8 in)
{
    /* Convert logical Genesis inputs to BC bits once per byte. This is ROM
     * data; both held and pressed inputs retain all simultaneous buttons. */
    _Static_assert(IN_RIGHT == 1 && IN_LEFT == 2 && IN_DOWN == 4 && IN_UP == 8 &&
        IN_FIRE_L == 0x10 && IN_FIRE_R == 0x20 && IN_WEAPON == 0x40 && IN_START == 0x80,
        "BC input table follows logical input bits");
    static const u8 mapped[256] = {
        0x00,0x20,0x80,0xa0,0x40,0x60,0xc0,0xe0,0x10,0x30,0x90,0xb0,0x50,0x70,0xd0,0xf0,
        0x02,0x22,0x82,0xa2,0x42,0x62,0xc2,0xe2,0x12,0x32,0x92,0xb2,0x52,0x72,0xd2,0xf2,
        0x01,0x21,0x81,0xa1,0x41,0x61,0xc1,0xe1,0x11,0x31,0x91,0xb1,0x51,0x71,0xd1,0xf1,
        0x03,0x23,0x83,0xa3,0x43,0x63,0xc3,0xe3,0x13,0x33,0x93,0xb3,0x53,0x73,0xd3,0xf3,
        0x04,0x24,0x84,0xa4,0x44,0x64,0xc4,0xe4,0x14,0x34,0x94,0xb4,0x54,0x74,0xd4,0xf4,
        0x06,0x26,0x86,0xa6,0x46,0x66,0xc6,0xe6,0x16,0x36,0x96,0xb6,0x56,0x76,0xd6,0xf6,
        0x05,0x25,0x85,0xa5,0x45,0x65,0xc5,0xe5,0x15,0x35,0x95,0xb5,0x55,0x75,0xd5,0xf5,
        0x07,0x27,0x87,0xa7,0x47,0x67,0xc7,0xe7,0x17,0x37,0x97,0xb7,0x57,0x77,0xd7,0xf7,
        0x08,0x28,0x88,0xa8,0x48,0x68,0xc8,0xe8,0x18,0x38,0x98,0xb8,0x58,0x78,0xd8,0xf8,
        0x0a,0x2a,0x8a,0xaa,0x4a,0x6a,0xca,0xea,0x1a,0x3a,0x9a,0xba,0x5a,0x7a,0xda,0xfa,
        0x09,0x29,0x89,0xa9,0x49,0x69,0xc9,0xe9,0x19,0x39,0x99,0xb9,0x59,0x79,0xd9,0xf9,
        0x0b,0x2b,0x8b,0xab,0x4b,0x6b,0xcb,0xeb,0x1b,0x3b,0x9b,0xbb,0x5b,0x7b,0xdb,0xfb,
        0x0c,0x2c,0x8c,0xac,0x4c,0x6c,0xcc,0xec,0x1c,0x3c,0x9c,0xbc,0x5c,0x7c,0xdc,0xfc,
        0x0e,0x2e,0x8e,0xae,0x4e,0x6e,0xce,0xee,0x1e,0x3e,0x9e,0xbe,0x5e,0x7e,0xde,0xfe,
        0x0d,0x2d,0x8d,0xad,0x4d,0x6d,0xcd,0xed,0x1d,0x3d,0x9d,0xbd,0x5d,0x7d,0xdd,0xfd,
        0x0f,0x2f,0x8f,0xaf,0x4f,0x6f,0xcf,0xef,0x1f,0x3f,0x9f,0xbf,0x5f,0x7f,0xdf,0xff,
    };
    return mapped[in];
}

static void __attribute__((noinline)) player_sound_nonzero(u8 source)
{
    u8 command = bc_audio_player_command(source);
    if (command == 255 || !sound_try_command(command)) { dbg_bc_native_sfx_dropped++; return; }
    dbg_bc_native_sfx_commands++;
    dbg_bc_native_sfx_mask |= (u32)1 << source;
}

static void __attribute__((noinline)) actor_sound_nonzero(u8 source)
{
    u8 command = bc_audio_actor_command(source);
    if (command == 255 || !sound_try_command(command)) { dbg_bc_native_actor_sfx_dropped++; return; }
    dbg_bc_native_actor_sfx_commands++;
    dbg_bc_native_actor_sfx_mask |= (u32)1 << source;
}

/* Most per-frame events carry no sound. Keep their guard at the caller and
 * leave command submission and counters in the uncommon nonzero path. */
static inline __attribute__((always_inline)) void player_sound(u8 source)
{
    if (source) player_sound_nonzero(source);
}

static inline __attribute__((always_inline)) void actor_sound(u8 source)
{
    if (source) actor_sound_nonzero(source);
}

static void actor_audio_event(u8 slot, const BcActorStepEvent *event, void *context)
{
    (void)slot; (void)context;
    bc_audio_actor_append(&actor_audio, event);
    if (event->boss_defeat == 2)
        bc_round_exit_final_begin(&round_exit, &audio_request, &resource->data);
}

static void party_contact(u8 id, const BcActorEvent *event, void *context)
{
    (void)context;
    if (event->score_pending) bc_score_enqueue(id ? &peer_scores[id-1] : &score, event->score_id, 1);
    if (event->sound) {
        if (actor_audio.count < BC_ACTOR_AUDIO_CAPACITY) actor_audio.sources[actor_audio.count++] = event->sound;
        else actor_audio.dropped++;
    }
}

/* Co-op respawns retain the shared stage/enemies while each robot spends its
 * own lives. The original 1P checkpoint path below remains unchanged. */
static BcFrameResult party_frame(void)
{
    u8 held[4] = {0}, pressed[4] = {0};
    for (u8 i = 0; i < party_count; i++) {
        held[i] = buttons(pad[i].held); pressed[i] = buttons(pad[i].pressed);
    }
    BcPartyFrameResult multi;
    bc_runtime_party_frame_into(&multi, &party_control, &cursor, actors, &stage,
        &stage_data, &actor_data, resource->pose_table, held, pressed, &limited_count, &events);
    for (u8 i = 0; i < party_count; i++) {
        player_sound(multi.players[i].control.sound);
        player_sound(multi.players[i].weapon.charge_sound);
        player_sound(multi.players[i].weapon.shot_sound);
        if (!(multi.checkpoints & (1 << i))) continue;
        BcPlayerControl *p = member(i);
        if (!(developer_active && developer_lives)) p->world.inventory.lives--;
        if (p->world.inventory.lives & 128) continue;
        p->world.inventory.weapon = p->world.inventory.power = 0;
        bc_player_reset(p, resource->round, &stage_data.data, resource->player_template);
        p->world.y = (64 + i*32) << 8;
        p->world.invulnerability = 200;
        party_control.waiting &= ~(1 << i);
        dbg_bc_native_party_respawns[i]++;
    }
    BcFrameResult result = {0};
    result.status = multi.status; result.handler = multi.handler;
    result.stage_events = multi.stage_events; result.play.next_slot = multi.next_slot;
    if (multi.status == 1) result.status = party_control.waiting == (1 << party_count)-1 ? 7 : 0;
    return result;
}

static void stage_birth_audio(u8 slot, const BcActorEvent *event, void *context)
{
    (void)slot; (void)context;
    if (!event->sound) return;
    if (actor_audio.count < BC_ACTOR_AUDIO_CAPACITY)
        actor_audio.sources[actor_audio.count++] = event->sound;
    else actor_audio.dropped++;
}

static void round_nine_event(u16 handler)
{
    static const u16 births[9] = {0xa574,0xb384,0xaff2,0xac32,0xc18b,0xa8c6,0xb8d4,0xbcf0,0xc539};
    static const u16 templates[9] = {0xa6d9,0xb656,0xb1ee,0xaeaa,0xc394,0xaae2,0xbb9e,0xbf23,0xc742};
    for (u8 i = 0; i < 9; i++) {
        if (handler != births[i]) continue;
        stage_data.boss_base = template_base(templates[i]);
        actor_data.boss_spread_base = base(i == 1 || i == 7 ? 0x36cc : i == 5 ? 0x36ce : i == 3 || i == 6 ? 0x36b4 : 0x36c8);
        actor_data.boss_beam_base = base(i == 6 ? 0x3698 : i == 4 ? 0x36ca : 0x36c8);
        bc_boss_art_queue_encounter(i);
        dbg_bc_native_encounter = i + 1;
        return;
    }
}

/* BC-specific colors are prepacked per asset. Preserve the Normal palette so
 * unchanged families (especially the Jet), players and HUD retain their colors. */
static void load_sprite_colors(void)
{
    pal_load(32, bc_sprite_pal, 32);
}

static void begin(u8 round, bool new_game)
{
    if (new_game && home_session) {
        credits = home_cfg.credits >= 1 && home_cfg.credits <= 9 ? home_cfg.credits-1 : 2;
        memset(continue_prompts, 0, sizeof(continue_prompts));
        memset(unused_continues, 5, sizeof(unused_continues));
        continue_pending = continue_shown = 0;
        const u32 *table = game_extend_table();
        home_extend_count = 0;
        if (game_cfg.bonus < BONUS_NONE) {
            while (home_extend_count < 6 && table[home_extend_count]) {
                u32 value = table[home_extend_count];
                for (s16 digit = 7; digit >= 0; digit--) {
                    home_extend_thresholds[home_extend_count][digit] = value % 10;
                    value /= 10;
                }
                home_extend_count++;
            }
        }
    }
    terminal_shown = FALSE; ending_bonus_phase = 0;
    resource = &bc_round_resources[round];
    dbg_bc_native_current_round = round;
    if (new_game) {
        memset(&player, 0, sizeof(player)); memset(&score, 0, sizeof(score));
        memset(score.queue, 255, sizeof(score.queue));
        party_count = dbg_bc_native_players >= 2 && dbg_bc_native_players <= 4 ? dbg_bc_native_players : 1;
        player_limit = party_count;
        if (party_count > 1) memset(peers, 0, (party_count-1)*sizeof(*peers));
        memset(peer_scores, 0, sizeof(peer_scores));
        for (u8 i = 0; i < 3; i++) memset(peer_scores[i].queue, 255, sizeof(peer_scores[i].queue));
        for (u8 i = 0; i < 4; i++) dbg_bc_native_party_respawns[i] = 0;
        seed = 1;
    }
    memset(actors, 0, sizeof(actors)); memset(&stage, 0, sizeof(stage));
    memset(&palette, 0, sizeof(palette)); memset(&audio_request, 0, sizeof(audio_request));
    memset(&round_exit, 0, sizeof(round_exit)); dbg_bc_native_round_exit = 0;
    memset(&defeat, 0, sizeof(defeat)); memset(&cursor, 0, sizeof(cursor));
    memset(&stage_data, 0, sizeof(stage_data)); memset(&actor_data, 0, sizeof(actor_data));
    limited_count = 0;
    if (new_game) scheduler_counter = 0;
    stage_data.data = actor_data.data = resource->data;
    bc_player_bind_poses(&resource->data, resource->pose_table);
    stage_data.round = actor_data.round = resource->round;
    stage_data.relocation = actor_data.relocation = resource->relocation;
    bc_actor_bind_segments(&actor_data);
    bool second = resource->round == 1, third = resource->round == 2, fourth = resource->round == 3, fifth = resource->round == 4, sixth = resource->round == 5, seventh = resource->round == 6, eighth = resource->round == 7, ninth = resource->round == 8, tenth = resource->round == 9;
    dbg_bc_native_encounter = 0;
    stage_data.prepare_event = ninth ? round_nine_event : NULL;
    startup_audio = bc_audio_round_start(&audio_request, &resource->data, resource->round);
    if (ninth) bc_palette_boss(&palette, &resource->data);
    s16 relocation = resource->relocation;
    stage_data.hover_base = tenth ? 0 : template_base(ninth ? 0xc9dd : eighth ? 0xb753 : seventh ? 0xb099 : sixth ? 0xb42a : fifth ? 0xb4a7 : fourth ? 0xafd7 : third ? 0xb0cf : second ? 0xb58e : 0xaca6);
    stage_data.curve_base = (ninth || tenth) ? 0 : template_base(eighth ? 0xb65e : seventh ? 0xafa4 : sixth ? 0xb7fd : fifth ? 0xb3b2 : fourth ? 0xaee2 : third ? 0xbccc : second ? 0xb91f : 0xae54);
    stage_data.hopper_base = (ninth || tenth) ? 0 : template_base(eighth ? 0xc28b : seventh ? 0xbdf0 : sixth ? 0xbd96 : fifth ? 0xbc2e : fourth ? 0xbc40 : third ? 0xb578 : second ? 0xb2df : 0xb213);
    stage_data.launcher_base = (ninth || tenth) ? 0 : template_base(seventh ? 0xbc1c : fifth ? 0xba5a : fourth ? 0xb2ae : third ? 0xb3cc : second ? 0xba33 : 0xb31d);
    stage_data.jumper_base = (ninth || tenth) ? 0 : template_base(eighth ? 0xb915 : seventh ? 0xb25b : sixth ? 0xb5ec : fifth ? 0xb669 : fourth ? 0xb199 : third ? 0xb291 : second ? 0xb750 : 0xb0a5);
    stage_data.item_base = template_base(0x8908 + relocation);
    stage_data.fast_curve_base = (ninth || tenth) ? 0 : template_base(eighth ? 0xb65e : seventh ? 0xafa4 : sixth ? 0xb335 : fifth ? 0xb3b2 : fourth ? 0xaee2 : third ? 0xafda : second ? 0xb499 : 0xabb1);
    stage_data.boss_base = tenth ? 0 : template_base(ninth ? 0xa6d9 : eighth ? 0xb279 : seventh ? 0xacd5 : sixth ? 0xb068 : fifth ? 0xae59 : fourth ? 0xa9e6 : third ? 0xacc7 : second ? 0xae67 : 0xb4b0);
    stage_data.score = &score; stage_data.playing = 1;
    stage_data.birth_sink = stage_birth_audio; stage_data.birth_context = NULL;
    stage_data.random_state = &seed;
    stage_data.fixed_turret_base = eighth ? template_base(0xbd5f) : fourth ? template_base(0xba8a) : third ? template_base(0xba9a) : 0;
    stage_data.walker_base = fifth ? template_base(0xb1f8) : fourth ? template_base(0xad28) : 0;
    stage_data.orbiter_base = eighth ? template_base(0xafb6) : sixth ? template_base(0xadbc) : 0;
    stage_data.terrain_jumper_base = sixth ? template_base(0xba57) : 0;
    stage_data.terrain_hopper_base = sixth ? template_base(0xbbc5) : 0;
    stage_data.turret_bases[0] = seventh ? template_base(0xb6bc) : 0;
    stage_data.turret_bases[1] = seventh ? template_base(0xb58d) : 0;
    stage_data.turret_bases[2] = seventh ? template_base(0xb370) : 0;
    actor_data.boss_beam_base = base(seventh ? 0x3698 : fifth ? 0x36ca : 0x36c8);
    stage_data.ceiling_base = eighth ? template_base(0xbb1a) : seventh ? template_base(0xbb1c) : fourth ? template_base(0xb59a) : third ? template_base(0xb9a5) : second ? template_base(0xbe93) : base(0x3682);
    for (u8 i = 0; i < 6; i++)
        stage_data.segment_bases[i] = tenth ? (i < 3 ? base(0x36d0 + i * 2) : 0) : base(0x369e + i * 2);
    stage_data.palette = &palette; stage_data.audio = &audio_request;
    actor_data.bullet_base = base(word(0x8aaf + relocation));
    actor_data.small_explosion_base = base(0x367c); actor_data.large_explosion_base = base(0x367e);
    actor_data.bullet_death_base = base(0x367a); actor_data.homing_inherited_base = base(0x3684);
    actor_data.boss_spread_base = base(eighth ? 0x36cc : seventh ? 0x36b4 : sixth ? 0x36ce : fourth ? 0x36b4 : second ? 0x36cc : 0x36c8);
    actor_data.homing_base = base(0x3682);
    actor_data.random_state = &seed; actor_data.terrain.cells = resource->data.bytes + 0xc000;
    events.score = &score; events.playing = 1; events.effects_only = 1; events.next = actor_audio_event; events.context = NULL; events.defeat = &defeat;
    bc_stage_checkpoint_initial(&stage, resource->header);
    bc_stage_checkpoint_restore(&stage, resource->header);
    bc_player_reset(&player, resource->round, &stage_data.data, resource->player_template);
    /* Source inventory stores spare robots: zero still permits the current
     * life. Home's shared setting counts total lives, like Normal/Boss Rush. */
    u8 initial_reserves = home_session ?
        (game_cfg.lives >= 1 && game_cfg.lives <= 7 ? game_cfg.lives - 1 : 2) : 3;
    if (new_game) player.world.inventory.lives = initial_reserves;
    BcPlayerControl *members[4] = {&player, NULL, NULL, NULL};
    for (u8 i = 1; i < party_count; i++) members[i] = member(i);
    for (u8 i = 1; i < party_count; i++) {
        bc_player_reset(members[i], resource->round, &stage_data.data, resource->player_template);
        if (new_game) members[i]->world.inventory.lives = initial_reserves;
    }
    bc_party_bind(&party_control, members, party_count, party_contact, NULL);
    if (party_count > 1) for (u8 i = 0; i < party_count; i++) {
        members[i]->world.y = (64 + i*32) << 8;
        if (members[i]->world.inventory.lives & 128) {
            members[i]->world.state = members[i]->entry = 0;
            party_control.waiting |= 1 << i;
        }
    }
    bc_robot_art_init(&art, &stage_data.data, resource->pose_table, player.death_script, DEATH_CODES);
    dbg_bc_native_status = dbg_bc_native_handler = 0;
    if (new_game) {
        dbg_bc_native_ticks = dbg_bc_native_events = 0;
        dbg_bc_native_resets = 0;
        dbg_bc_native_actor_sfx_commands = dbg_bc_native_actor_sfx_dropped = 0;
        dbg_bc_native_actor_sfx_mask = 0;
        dbg_bc_native_sfx_commands = dbg_bc_native_sfx_dropped = 0; dbg_bc_native_sfx_mask = 0;
        dbg_bc_native_music_command = 255; dbg_bc_native_music_requests = 0;
    }
    hud_suspend();
    SYS_setVBlankCallback(NULL);
    VDP_setEnable(FALSE); VDP_setWindowVPos(FALSE, 0);
    VDP_setScrollingMode(HSCROLL_PLANE, VSCROLL_PLANE);
    VDP_clearPlane(BG_A, TRUE); VDP_clearPlane(BG_B, TRUE); VDP_clearPlane(WINDOW, TRUE);
    VDP_setHorizontalScroll(BG_A, 0); VDP_setHorizontalScroll(BG_B, 0);
    VDP_setVerticalScroll(BG_A, 0); VDP_setVerticalScroll(BG_B, 0);
    PAL_setColor(0, 0); spr_init(); load_sprite_colors();
    bg_release_blocks(); bg_init();
    const Zone *scenery = tenth ? &bc_bg10_draft : ninth ? &bc_bg9_draft : eighth ? &bc_bg8_draft : seventh ? &bc_bg7_draft : sixth ? &bc_bg6_draft : fifth ? &bc_bg5_draft : fourth ? &bc_bg4_draft : third ? &bc_bg3_draft : second ? &bc_bg2_draft : &bc_bg_draft;
    const u16 *remap = tenth ? bc_bg10_remap : ninth ? bc_bg9_remap : eighth ? bc_bg8_remap : seventh ? bc_bg7_remap : sixth ? bc_bg6_remap : fifth ? bc_bg5_remap : fourth ? bc_bg4_remap : third ? bc_bg3_remap : second ? bc_bg2_remap : bc_bg_remap;
    dbg_bc_native_background_active = !dbg_bc_native_background_off && scenery && remap;
    if (dbg_bc_native_background_active) {
        bg_set_stage(scenery, resource->data.bytes + 0xc000, remap, bc_bg_sources, (fourth || fifth || seventh) ? 16 : second ? 0x8010 : round == 0 ? ((78 << 8) | 16) : round == 2 ? 0x8000 : 0);
        bg_enable(TRUE);
    }
    if (!dbg_bc_native_background_active) bg_enable(FALSE);
    if (ninth) bc_boss_art_init_sequence(); else bc_boss_art_init_round(resource->round);
    bc_hud_show_total_lives(home_session);
    if (party_count > 1) bc_hud_party_begin(party_count); else bc_hud_begin();
    VDP_setEnable(TRUE);
}

/* First ending page. Gameplay is already stopped at the verified final
 * handoff. Gallery/credits will consume phase 3 after their renderer is wired. */
static bool continue_available(void)
{
    return game_cfg.allow_continue && game_cfg.cont != CONT_OFF &&
        (game_cfg.cont == CONT_UNLIMITED || credits);
}

static void continue_update(void)
{
    continue_pending = 0;
    if (dbg_bc_native_status == 6) return;
    bool restart = dbg_bc_native_status == 7, accepted = FALSE;
    for (u8 i = 0; i < party_count; i++) {
        BcPlayerControl *p = member(i);
        BcContinue *prompt = &continue_prompts[i];
        if (!(p->world.inventory.lives & 128)) { prompt->state = 0; continue; }
        if (!prompt->state) bc_continue_begin(prompt, continue_available());
        else if (prompt->state == BC_CONT_WAITING) {
            if (!continue_available()) prompt->state = BC_CONT_EXPIRED;
            else bc_continue_tick(prompt, pad[i].pressed & IN_START);
        }
        if (prompt->state == BC_CONT_ACCEPTED) {
            if (game_cfg.cont != CONT_UNLIMITED) credits--;
            if (unused_continues[i]) unused_continues[i]--;
            bc_score_continue(i ? &peer_scores[i-1] : &score);
            p->world.inventory.lives = game_cfg.lives >= 1 && game_cfg.lives <= 7 ? game_cfg.lives-1 : 2;
            /* The source continue bypasses the ordinary-death weapon clear;
             * the final round's reset intentionally preserves this loadout. */
            if (resource->round != 9) p->world.inventory.weapon = p->world.inventory.power = 0;
            if (!restart) {
                bc_player_reset(p, resource->round, &stage_data.data, resource->player_template);
                p->world.y = (64+i*32) << 8;
                p->world.invulnerability = 200;
                party_control.waiting &= ~(1 << i);
            }
            prompt->state = 0; accepted = TRUE;
            pad[i].pressed &= ~IN_START;
        } else if (prompt->state == BC_CONT_WAITING) {
            continue_pending |= 1 << i;
            pad[i].pressed &= ~IN_START;
        }
    }
    if (restart && accepted) begin(resource->round, FALSE);
}

static void continue_draw(void)
{
    if (!continue_pending && !continue_shown) return;
    for (u8 i = 0; i < 4; i++) {
        hud_blank(0, 3+i, HUD_COLS);
        if (!(continue_pending & (1 << i))) continue;
        char label[] = "P1 CONTINUE? START"; label[1] += i;
        hud_text(4, 3+i, 0, label);
        hud_number(24, 3+i, 4, continue_prompts[i].digit, 1);
    }
    hud_blank(0, 7, HUD_COLS);
    if (continue_pending) {
        if (game_cfg.cont == CONT_UNLIMITED) hud_text(10, 7, 0, "UNLIMITED CONTINUES");
        else { hud_text(10, 7, 0, "CREDITS"); hud_number(20, 7, 0, credits, 1); }
    }
    VDP_setWindowVPos(FALSE, continue_pending ? 8 : party_count > 2 ? 2 : 1);
    continue_shown = continue_pending;
    hud_frame();
}

static void ending_total(u8 id, u8 row)
{
    BcScore *s = id ? &peer_scores[id-1] : &score;
    u16 codes[8];
    for (u8 j = 0; j < 8; j++) codes[j] = s->digits[j];
    hud_codes(23, row, 0, codes, 8);
}

static void submit_music(void)
{
    if (!dbg_bc_native_audio_manual && audio_request.state == 1) {
        u8 command = bc_audio_music_command(&audio_request, stage_data.relocation);
        if (command != 255 && sound_try_command(command)) {
            bc_audio_acknowledge(&audio_request);
            dbg_bc_native_music_command = command;
            dbg_bc_native_music_requests++;
        }
    }
}

/* The gallery has no scenery, freeing banks 0/1 for a mint-metal variant
 * of our own sprite ramps. No source patterns or additional raster work. */
static void gallery_colors(void)
{
    u16 colors[32];
    for (u8 i = 0; i < 32; i++) {
        /* Normal's spare shade pens are not part of the original gallery ramp. */
        u16 c = (i & 15) == 15 ? 0 : sprite_pal[i];
        u16 light = (((c & 14)*3 + ((c >> 4)&14)*6 + ((c >> 8)&14))/10)&14;
        /* BC palette 15 uses gold portraits. Quantize the same ramp used
         * while packing BC gallery variants; gameplay palettes stay intact. */
        u16 green = light == 14 ? 14 : (light*5/14)*2;
        u16 blue = light == 14 ? 14 : (light*2/14)*2;
        colors[i] = (i & 15) ? light | (green << 4) | (blue << 8) : 0;
    }
    pal_load(0, colors, 32);
}

/* Gallery text occupies freed scenery tiles and two alternating 32-column
 * pages. Mark codes overprint the row above the previous character. */
static void gallery_text(u16 *cells, const u8 *bytes, u16 length, u16 left, u16 top)
{
    u16 x = left, y = top;
    for (u16 i = 0; i < length; i++) {
        u8 code = bytes[i];
        if (code == '/') { x = left; y++; continue; }
        u16 col = x, row = y;
        if (code == 0xba || code == 0xbb) { col--; row--; }
        else x++;
        if (col < 32 && row < 32 && code >= 0x20 && code <= 0xbc)
            cells[row*32+col] = TILE_ATTR_FULL(PAL3, 0, 0, 0, 160+code-0x20);
    }
}

static void gallery_caption(u8 entry)
{
    /* Background streaming is suspended through the ending. Reuse its RAM
     * page: a 2 KiB stack array would overlap the four-player heap. */
    u16 *cells = bg_scene_page();
    if (entry < 20) {
        const BcEndingCaption *caption = &bc_gallery_captions[entry];
        gallery_text(cells, bc_gallery_frame, sizeof(bc_gallery_frame), 4, 6);
        gallery_text(cells, caption->bytes, caption->length, 11, 4);
    }
    VDP_setTileMapDataRect(BG_B, cells, ((entry+1)&1)*32, 0, 32, 32, 32, DMA_QUEUE_COPY);
}

static void ending_bonus_draw(void)
{
    /* Original credits CD range: 8,473 sectors at 75Hz. Match its finite
     * playback window on the 60Hz ending clock, including the input wait. */
    if ((ending_bonus_phase == 6 || ending_bonus_phase == 7) && ending_music_clock < 6778)
        if (++ending_music_clock == 6778) sound_command(SOUND_BC_CREDITS_STOP);
    submit_music();
    if (!ending_bonus_phase) {
        /* Final clear reaches $6042: stop audio and fade the current screen
         * before the ending overlay replaces it with the bonus presentation. */
        sound_stop_all();
        ending_bonus_clock = 0;
        ending_bonus_phase = 10;
        return;
    } else if (ending_bonus_phase == 10) {
        if (!(++ending_bonus_clock % 3)) pal_fade_level(7-ending_bonus_clock / 3);
        if (ending_bonus_clock == 21) ending_bonus_phase = 11;
        return;
    } else if (ending_bonus_phase == 11) {
        bg_enable(FALSE); spr_bc_begin(); spr_end();
        VDP_clearPlane(BG_A, TRUE); VDP_clearPlane(BG_B, TRUE);
        gallery_colors();
        VDP_loadTileData(bc_caption_tiles, 160, 157, DMA_QUEUE);
        hud_begin_fixed(28);
        for (u8 row = 0; row < 28; row++) hud_blank(0, row, HUD_COLS);
        hud_text(12, 3, 4, "CONGRATULATIONS!");
        hud_text(13, 5, 0, "SPECIAL BONUS");
        ending_bonus_clock = 0;
        for (u8 i = 0; i < party_count; i++) {
            BcPlayerControl *p = member(i);
            BcScore *s = i ? &peer_scores[i-1] : &score;
            u8 row = 8+i*4;
            char label[3] = {'P', '1'+i, 0};
            hud_text(2, row, 0, label);
            ending_robots[i] = p->world.inventory.lives & 128 ? 0 : p->world.inventory.lives+1;
            hud_number(6, row, 0, ending_robots[i], 3);
            hud_text(10, row, 0, "X"); hud_number(12, row, 0, (u32)10000 << unused_continues[i], 6);
            hud_text(20, row, 0, "="); hud_number(23, row, 0, 0, 8);
            hud_text(15, row+1, 0, "TOTAL"); ending_total(i, row+1);
            ending_bonus_units[i] = bc_score_completion_bonus(s, p->world.inventory.lives, unused_continues[i]);
            for (u8 j = 0; j < 8; j++) {
                if (s->digits[j] < s->high[j]) break;
                if (s->digits[j] > s->high[j]) { memcpy(s->high, s->digits, 8); break; }
            }
        }
        pal_fade_level(0);
        ending_bonus_phase = 8;
    } else if (ending_bonus_phase == 8) {
        /* $4190: seven levels, each following a three-frame wait. */
        if (!(++ending_bonus_clock % 3)) pal_fade_level(ending_bonus_clock / 3);
        if (ending_bonus_clock == 21) {
            ending_bonus_clock = 0;
            ending_bonus_phase = 1;
        }
    } else if (ending_bonus_phase == 1) {
        ending_bonus_clock++;
        u8 complete = 1, counting = 0;
        for (u8 i = 0; i < party_count; i++) {
            u16 units = ending_bonus_units[i];
            /* The source's three-digit counter increments before comparing:
             * a living player's zero total takes one full 1,000-step cycle.
             * Eliminated co-op rows have no robots and do not count. */
            u16 duration = !units && ending_robots[i] ? 1000 : units;
            if (ending_bonus_clock <= duration) {
                counting = 1;
                hud_number(23, 8+i*4, 0,
                    ending_bonus_clock == 1000 ? 0 : (u32)ending_bonus_clock*10000, 8);
            }
            if (ending_bonus_clock < duration) complete = 0;
        }
        /* Source $6136 requests one cue before each one-frame count step.
         * Co-op tallies share the cue rather than issuing it per player. */
        if (counting) actor_sound(2);
        if (complete) {
            for (u8 i = 0; i < party_count; i++) ending_total(i, 9+i*4);
            ending_bonus_clock = 180; ending_bonus_phase = 2;
        }
    } else if (ending_bonus_phase == 2) {
        /* $6215 stops PSG effects after the final counted frame. */
        if (ending_bonus_clock == 180) sound_command(SOUND_STOP_SFX);
        if (--ending_bonus_clock) { hud_frame(); return; }
        ending_bonus_phase = 9;
    } else if (ending_bonus_phase == 9) {
        /* $41A1: levels six through zero, three frames apart. */
        if (!(++ending_bonus_clock % 3)) pal_fade_level(7-ending_bonus_clock / 3);
        if (ending_bonus_clock < 21) { hud_frame(); return; }
        hud_begin_fixed(0);
        VDP_setScrollingMode(HSCROLL_PLANE, VSCROLL_PLANE);
        VDP_setVerticalScroll(BG_B, 0);
        VDP_setHorizontalScroll(BG_B, 32);
        gallery_caption(0);
        pal_fade_level(7);
        bc_audio_ending_request(&audio_request, 0);
        bc_gallery_begin(&ending_gallery, actors);
        ending_gallery_limited = 0;
        ending_bonus_phase = 3;
    } else if (ending_bonus_phase == 3) {
        u8 result = bc_gallery_tick(&ending_gallery, actors, &bc_gallery_data,
            bc_gallery_bases, &ending_gallery_limited);
        if (result == 2) gallery_caption(ending_gallery.entry);
        VDP_setHorizontalScroll(BG_B, 32-ending_gallery.camera_x);
        spr_bc_begin();
        dbg_bc_native_actor_unmapped = bc_gallery_draw(actors, 32, 0);
        spr_end();
        if (result == 3) {
            ending_bonus_phase = 4;
            ending_bonus_clock = 180;
            sound_stop_all();
        }
    } else if (ending_bonus_phase == 4 && !--ending_bonus_clock) {
        ending_bonus_phase = 5;
    } else if (ending_bonus_phase == 5) {
        bc_audio_ending_request(&audio_request, 1);
        hud_begin_fixed(0);
        VDP_clearPlane(BG_A, TRUE); VDP_clearPlane(BG_B, TRUE);
        VDP_setScrollingMode(HSCROLL_PLANE, VSCROLL_PLANE);
        VDP_setHorizontalScroll(BG_A, 0); VDP_setVerticalScroll(BG_A, 0);
        ending_credit_clock = ending_music_clock = 0;
        ending_bonus_phase = 6;
    } else if (ending_bonus_phase == 6) {
        /* $9A33: sixteen half-pixel steps, each followed by two frames,
         * per slash-delimited source row. Queue the next row below view. */
        u16 row = ending_credit_clock >> 5;
        if (!(ending_credit_clock & 31))
            hud_plane_text_row(BG_A, (row+31)&31, 8, 0, bc_credit_rows[row]);
        VDP_setVerticalScroll(BG_A, (ending_credit_clock+2) >> 2);
        if (++ending_credit_clock == (bc_credit_row_count-1)*32) {
            ending_bonus_phase = 7;
        }
    }
    hud_frame();
}


void bc_scene_start(u8 players)
{
    dbg_bc_native_players = players >= 1 && players <= 4 ? players : 1;
    dbg_bc_native_start_round = 0;
    dbg_bc_native_background_off = dbg_bc_native_protect = 0;
    dbg_bc_native_hold_exit = dbg_bc_native_audio_manual = dbg_bc_native_audio_ack = 0;
    dbg_bc_native_die = dbg_bc_native_die_mask = dbg_bc_native_boss_defeat = 0;
    flow_session_request_bc();
}

u8 bc_scene_control(void)
{
    bool reset = (pad[0].held & 0xf0) == 0xf0 && pad[0].pressed;
    if (!reset && !scene_paused &&
        (continue_pending || party_control.waiting || dbg_bc_native_status == 7)) continue_update();
    bool finished = dbg_bc_native_status == 7 ||
        (dbg_bc_native_status == 6 && resource->round == 9);
    u8 ending_input = 0;
    for (u8 i = 0; i < party_count; i++) ending_input |= pad[i].pressed;
    if (reset || (finished && ((dbg_bc_native_status == 7 && !continue_pending && (pad[0].pressed & IN_START)) ||
        (ending_bonus_phase == 7 && ending_input)))) {
        return reset ? SESSION_RESET : SESSION_HOME;
    } else if (!finished && (scene_paused || !round_exit.pause_disabled)) {
        u8 pressed = 0;
        for (u8 i = 0; i < party_count; i++)
            if (!(member(i)->world.inventory.lives & 128)) pressed |= pad[i].pressed;
        if (pressed & IN_START) {
            return SESSION_PAUSE;
        }
    }
    return SESSION_RUN;
}

void bc_scene_pause_display(void)
{
    hud_blank(0, 2, HUD_COLS);
    if (scene_paused) hud_text(13, 2, 0, "PAUSED - START");
    VDP_setWindowVPos(FALSE, scene_paused ? 3 : party_count > 2 ? 2 : 1);
    hud_frame();
}

bool bc_scene_available(void) { return bc_round_resources != NULL; }

void bc_scene_enter(void)
{
    begin(dbg_bc_native_start_round <= 9 ? dbg_bc_native_start_round : 0, TRUE);
}

/* Ordered BC behavior/presentation policy. Session lifetime, controls, clock,
 * frame completion and resource handoff are owned by the regular engine. */
/* Keep BC scene locals out of the shared game-loop register/stack frame. */
bool bc_frame_presented;
bool bc_scene_can_skip(void)
{
    if (!party_count || scene_paused || startup_audio || continue_pending || continue_shown ||
        terminal_shown || ending_bonus_phase || round_exit.phase || dbg_bc_native_status)
        return FALSE;
    return TRUE;
}

void __attribute__((noinline)) bc_scene_frame(void)
{
    bc_damage_disabled = developer_active && developer_invincible;
    bc_frame_presented = TRUE;
    /* Keep the completed clear boundary observable for one frame, then load
     * the next supported round. Later rounds remain explicit handoffs. */
    if (dbg_bc_native_status == 6 && !dbg_bc_native_hold_exit && resource->round < 9)
        begin(resource->round + 1, FALSE);
    bool profiling = dbg_bc_native_profile_on != 0;
    u32 started = profiling ? profile_clock() : 0, simulation = started;
    if (dbg_bc_native_status == 0 || dbg_bc_native_status == 4) {
        scheduler_counter++;
        actor_data.scheduler_counter = scheduler_counter;
        BcScoreEvent score_event = home_session ?
            bc_score_step_extends(&score, &seed, &player.world.inventory.lives,
                home_extend_thresholds, home_extend_count) :
            bc_score_step(&score, &seed, &player.world.inventory.lives);
        if (score_event.life_awarded) actor_sound(score_event.sound);
        for (u8 i = 1; i < party_count; i++) {
            /* The shared RNG already advanced for player one. */
            score_event = home_session ? bc_score_step_extends(&peer_scores[i-1], NULL,
                &peers[i-1].world.inventory.lives, home_extend_thresholds, home_extend_count) :
                bc_score_step(&peer_scores[i-1], NULL, &peers[i-1].world.inventory.lives);
            if (score_event.life_awarded) actor_sound(score_event.sound);
        }
        submit_music();
        if (dbg_bc_native_audio_ack) {
            bc_audio_acknowledge(&audio_request);
            dbg_bc_native_audio_ack = 0;
        }
        if (startup_audio) {
            if (audio_request.state != 2) {
                dbg_bc_native_status = 4;
                goto draw_scene;
            }
            startup_audio = 0; audio_request.state = 0;
        }
        if (dbg_bc_native_boss_defeat && resource->round == 9) {
            for (u8 i = 0; i < 8; i++) {
                if (actors[i].body.state != 0x80 || actors[i].dash_started != 0x48 ||
                    actors[i].sprite_base_ref != 0x36d0) continue;
                actors[i].body.state = 0x40;
                dbg_bc_native_boss_defeat = 0;
                break;
            }
        }
        if (dbg_bc_native_boss_defeat && actors[0].body.state == 0x80 &&
            (resource->round == 8 || actors[0].sprite_base_ref == (resource->round == 7 ? 0x36c0 : resource->round == 6 ? 0x36c6 : resource->round == 5 ? 0x36ba : resource->round == 4 ? 0x36b8 : resource->round == 3 ? 0x36be : resource->round == 2 ? 0x36bc : resource->round == 1 ? 0x36c4 : 0x36b6))) {
            actors[0].body.state = 0x40;
            dbg_bc_native_boss_defeat = 0;
        }
        BcDefeatTaskResult ending = bc_runtime_defeat_step(&defeat, &stage, actors,
            &player.world, &actor_data.data, resource->relocation, base(0x367e), &seed, &limited_count, 0, &events);
        actor_sound(ending.actor_event.sound);
        if (ending.completion == 2)
            bc_round_exit_begin(&round_exit, &audio_request, &actor_data.data, actor_data.relocation);
        if (bc_round_exit_tick(&round_exit, &audio_request, 0))
            dbg_bc_native_status = 6; /* clear delay complete; load on the next frame */
        else {
            for (u8 i = 0; i < party_count; i++) {
                BcPlayerControl *p = member(i);
                if (dbg_bc_native_protect) p->world.invulnerability = 200;
                if ((dbg_bc_native_die_mask & (1 << i)) && !p->entry && p->world.state == 0x80) {
                    p->world.state = 0x40; dbg_bc_native_die_mask &= ~(1 << i);
                }
            }
            if (dbg_bc_native_die && !player.entry && player.world.state == 0x80) {
                player.world.state = 0x40;
                dbg_bc_native_die = 0;
            }
            if (profiling) {
                simulation = profile_clock();
                dbg_bc_native_profile[0] = simulation - started;
            }
            actor_audio.count = actor_audio.dropped = 0;
            BcFrameResult result = party_count > 1 ? party_frame() : bc_runtime_frame(&cursor, &player, actors, &stage,
                &stage_data, &actor_data, resource->pose_table, buttons(pad[0].held), buttons(pad[0].pressed),
                &limited_count, &events);
            player_sound(result.play.player_event.control.sound);
            player_sound(result.play.player_event.weapon.charge_sound);
            player_sound(result.play.player_event.weapon.shot_sound);
            for (u16 i = 0; i < actor_audio.count; i++) actor_sound(actor_audio.sources[i]);
            dbg_bc_native_actor_sfx_dropped += actor_audio.dropped;
            dbg_bc_native_status = result.status;
            dbg_bc_native_handler = result.status == 2 ? actors[result.play.next_slot].routine : result.handler;
            dbg_bc_native_events += result.stage_events;
            if (!result.status) dbg_bc_native_ticks++;
            else if (result.status == 1) {
                /* $638B-$63A2: remaining lives underflow ends the run. */
                if (!(developer_active && developer_lives)) player.world.inventory.lives--;
                if (player.world.inventory.lives & 0x80) dbg_bc_native_status = 7;
                else {
                    player.world.inventory.weapon = player.world.inventory.power = 0;
                    bc_runtime_checkpoint_reset(&cursor, &player, actors, &stage,
                        &stage_data.data, resource->round, resource->player_template, resource->header, &limited_count);
                    memset(&defeat, 0, sizeof(defeat));
                    memset(&audio_request, 0, sizeof(audio_request));
                    memset(&round_exit, 0, sizeof(round_exit));
                    dbg_bc_native_status = 0;
                    dbg_bc_native_resets++;
                }
            }
        }
    }
draw_scene:;
    if (home_session && dbg_bc_native_status == 6 && resource->round == 9) {
        ending_bonus_draw();
        return;
    }
    u32 drawing = profiling ? profile_clock() : 0;
    if (profiling) dbg_bc_native_profile[1] = drawing - simulation;
    dbg_bc_native_lives = player.world.inventory.lives;
    dbg_bc_native_round_exit = round_exit.phase;
    dbg_bc_native_camera[0] = stage.x >> 8; dbg_bc_native_camera[1] = stage.y >> 8;
    dbg_bc_native_position[0] = player.world.x >> 8; dbg_bc_native_position[1] = player.world.y >> 8;

    /* A queued transfer may refer to mutable frame storage. Flush that
     * presentation before advancing simulation again. */
    if (!engine_present && bc_scene_can_skip() && !DMA_getQueueSize()) {
        bc_frame_presented = FALSE;
        return;
    }

    if (dbg_bc_native_background_active) {
        /* The original 256px play area is centered in our 320px viewport. */
        bg_set_camera((s16)(stage.x >> 8) - 32, stage.y >> 8);
        bg_update();
    }
    u32 draw_split = profiling ? profile_clock() : 0;
    if (profiling) dbg_bc_native_draw_profile[0] = draw_split - drawing;
    spr_bc_begin();
    dbg_bc_native_unmapped = 0;
    for (u8 i = 0; i < party_count; i++) {
        BcPlayerControl *p = member(i);
        dbg_bc_native_party_position[i][0] = p->world.x >> 8;
        dbg_bc_native_party_position[i][1] = p->world.y >> 8;
        dbg_bc_native_party_lives[i] = p->world.inventory.lives;
        if (!terminal_shown) {
            /* Round five's pool lies between the two descents at x=1280/2816,
             * below the surface at world y=1232. Wait until the head is under. */
            u16 wx = (stage.x + p->world.x) >> 8;
            u16 wy = (stage.y + p->world.y) >> 8;
            bool submerged = resource->round == 4 && wx >= 1280 && wx < 3072 && wy >= 1248;
            dbg_bc_native_unmapped += !bc_robot_draw(&art, p, i, 32, 0, submerged);
            dbg_bc_native_unmapped += bc_projectiles_draw(&p->world.weapons, 32, 0);
        }
    }
    if (profiling) {
        u32 now = profile_clock();
        dbg_bc_native_draw_profile[1] = now - draw_split; draw_split = now;
    }
    if (terminal_shown) {
        u16 live_actors = 0;
        for (u16 i = 0; i < BC_ACTOR_CAPACITY; i++) if (actors[i].body.state) live_actors++;
        dbg_bc_native_actors = live_actors;
        dbg_bc_native_actor_unmapped = 0;
    } else {
        u16 counts = bc_actors_draw(actors, 32, 0);
        dbg_bc_native_actors = counts >> 8;
        dbg_bc_native_actor_unmapped = counts & 255;
    }
    if (profiling) {
        u32 now = profile_clock();
        dbg_bc_native_draw_profile[2] = now - draw_split; draw_split = now;
    }
    if (continue_pending) spr_under_window(64);
    spr_end();
    if (party_count > 1) {
        const BcScore *scores[4] = {&score, &peer_scores[0], &peer_scores[1], &peer_scores[2]};
        u8 lives[4];
        for (u8 i = 0; i < party_count; i++) lives[i] = member(i)->world.inventory.lives;
        bc_hud_party_draw(scores, lives, party_count);
    } else bc_hud_draw(&score, player.world.inventory.lives);
    if (home_session && dbg_bc_native_status == 7 && continue_available()) {
        for (u8 i = 0; i < party_count; i++) if (!continue_prompts[i].state &&
            (member(i)->world.inventory.lives & 128)) {
            bc_continue_begin(&continue_prompts[i], 1);
            continue_pending |= 1 << i;
        }
    }
    if (home_session) continue_draw();
    if (home_session && !continue_pending && !terminal_shown && (dbg_bc_native_status == 7 ||
        (dbg_bc_native_status == 6 && resource->round == 9))) {
        terminal_shown = TRUE;
        VDP_setWindowVPos(FALSE, 16);
        for (u8 row = 2; row < 16; row++) hud_blank(0, row, HUD_COLS);
        hud_text(14, 12, 4, dbg_bc_native_status == 7 ? "GAME OVER" : "GAME CLEAR");
        hud_text(10, 14, 0, "START - HOME MENU");
        hud_frame();
    }

    if (profiling) {
        u32 now = profile_clock();
        dbg_bc_native_draw_profile[3] = now - draw_split;
        dbg_bc_native_profile[2] = now - drawing;
    }
    return;
}
