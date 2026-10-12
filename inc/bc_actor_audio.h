#pragma once
#include "bc_world.h"
#define BC_ACTOR_AUDIO_CAPACITY 128
typedef struct {
    unsigned char sources[BC_ACTOR_AUDIO_CAPACITY];
    unsigned short count, dropped;
} BcActorAudio;
/* Retain event order without executing sound-driver work inside simulation. */
void bc_audio_actor_append(BcActorAudio *queue, const BcActorStepEvent *event);
