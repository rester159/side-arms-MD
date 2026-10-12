#include "bc_audio.h"

unsigned char bc_audio_stage_handler(unsigned short canonical)
{
    return canonical >= 0x8c50 && canonical <= 0x8d61 &&
        (canonical - 0x8c50) % 21 == 0;
}

void bc_audio_request(BcAudioRequest *request, const BcEnemyData *data,
    unsigned short handler)
{
    const unsigned char *source = data->bytes + (unsigned short)(handler + 5 - data->origin);
    request->handler = handler;
    for (unsigned char i = 0; i < 8; i++) request->parameters[i] = source[i];
    request->state = 1;
}

unsigned char bc_audio_round_start(BcAudioRequest *request, const BcEnemyData *data, unsigned char round)
{
    if (round != 8) return 0;
    bc_audio_request(request, data, 0x66f6);
    return 1;
}

void bc_audio_acknowledge(BcAudioRequest *request)
{
    if (request->state == 1) request->state = 2;
}

/* Ending overlay $9850 and $9989: gallery then staff roll. */
static const unsigned char ending_parameters[2][8] = {
    {0x03,0x22,0x33,0x40,0x05,0x56,0x40,0x43},
    {0x44,0x44,0x19,0x40,0x46,0x37,0x17,0x43}
};

void bc_audio_ending_request(BcAudioRequest *request, unsigned char credits)
{
    unsigned char index = credits != 0;
    request->handler = index ? 0x9989 : 0x9850;
    for (unsigned char i = 0; i < 8; i++) request->parameters[i] = ending_parameters[index][i];
    request->state = 1;
}

unsigned char bc_audio_music_command(const BcAudioRequest *request, signed short relocation)
{
    if (request->handler == 0x9850 || request->handler == 0x9989) {
        unsigned char index = request->handler == 0x9989;
        for (unsigned char i = 0; i < 8; i++)
            if (request->parameters[i] != ending_parameters[index][i]) return 255;
        return index ? 0xfe : 0x21;
    }
    static const unsigned char parameters[16][8] = {
        {0x03,0x22,0x33,0x40,0x05,0x56,0x40,0x41},
        {0x05,0x56,0x40,0x40,0x08,0x09,0x40,0x41},
        {0x08,0x09,0x40,0x40,0x08,0x15,0x33,0x43},
        {0x22,0x50,0x27,0x40,0x26,0x00,0x21,0x41},
        {0x26,0x00,0x21,0x40,0x28,0x19,0x28,0x41},
        {0x38,0x22,0x21,0x40,0x41,0x16,0x22,0x41},
        {0x36,0x10,0x16,0x40,0x38,0x22,0x21,0x41},
        {0x28,0x19,0x28,0x40,0x33,0x30,0x18,0x41},
        {0x33,0x35,0x01,0x40,0x36,0x10,0x16,0x41},
        {0x11,0x14,0x15,0x40,0x14,0x14,0x43,0x41},
        {0x14,0x14,0x43,0x40,0x16,0x52,0x35,0x41},
        {0x08,0x15,0x33,0x40,0x11,0x14,0x15,0x41},
        {0x16,0x52,0x35,0x40,0x20,0x08,0x69,0x41},
        {0x20,0x08,0x69,0x40,0x22,0x50,0x27,0x41},
        {0x41,0x16,0x22,0x40,0x44,0x37,0x38,0x41},
        {0x44,0x37,0x38,0x40,0x44,0x44,0x19,0x43}
    };
    unsigned short canonical = request->handler - relocation;
    unsigned char index;
    if (request->handler == 0x66f6 && relocation == -535) index = 13;
    else if (request->handler == 0xa5ff && relocation == -535) index = 15;
    else if (canonical == 0x8d0d) index = 14;
    else if (canonical == 0x8c50) index = 0;
    else if (canonical == 0x8d22) index = 1;
    else if (canonical == 0x8db2) index = 2;
    else if (canonical == 0x8c65) index = 3;
    else if (canonical == 0x8d61) index = 4;
    else if (canonical == 0x8c7a) index = 5;
    else if (canonical == 0x8d37) index = 6;
    else if (canonical == 0x8c8f) index = 7;
    else if (canonical == 0x8ca4) index = 8;
    else if (canonical == 0x8cb9) index = 9;
    else if (canonical == 0x8d4c) index = 10;
    else if (canonical == 0x8cce) index = 11;
    else if (canonical == 0x8ce3) index = 12;
    else return 255;
    for (unsigned char i = 0; i < 8; i++)
        if (request->parameters[i] != parameters[index][i]) return 255;
    /* Our existing finite jingle replaces the PCE clear track. */
    static const unsigned char commands[16] = {0x21,0x32,0x2a,0x22,0x32,0x23,0x32,0x24,0x25,0x26,0x32,0x27,0x28,0x29,0x36,0x2c};
    return commands[index];
}

unsigned char bc_audio_player_command(unsigned char source)
{
    switch (source) {
    case 0: return 0;
    case 1: return 0x01;  /* released short charge */
    case 3: return 0x0f;  /* player crushed/destroyed */
    case 5: return 0x01;  /* ordinary shot */
    case 6: return 0x03;  /* returning weapon */
    case 7: return 0x04;  /* charged beam */
    case 0x17: return 0x05; /* charge-ready cue */
    default: return 255;
    }
}

unsigned char bc_audio_actor_command(unsigned char source)
{
    switch (source) {
    case 0: return 0;
    case 2: return 0x17; /* ending bonus count: short Genesis tick */
    case 3: return 0x0f; /* player contact death */
    case 4: return 0x11; /* explosion or boss damage */
    case 8: return 0x1c; /* pickup */
    case 12: return 0x12; /* option absorbs a hit */
    case 13: return 0x14; /* boss defeat */
    case 22: return 0x1d; /* extra life */
    default: return 255;
    }
}
