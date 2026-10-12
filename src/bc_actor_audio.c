#include "bc_actor_audio.h"

static void append(BcActorAudio *queue, unsigned char source)
{
    if (!source) return;
    if (queue->count < BC_ACTOR_AUDIO_CAPACITY) queue->sources[queue->count++] = source;
    else queue->dropped++;
}

void bc_audio_actor_append(BcActorAudio *queue, const BcActorStepEvent *event)
{
    append(queue, event->setup_sound);
    for (unsigned char i = 0; i < event->extra_count; i++) append(queue, event->extra_events[i].sound);
    append(queue, event->child_event.sound);
    append(queue, event->actor_event.sound);
}
