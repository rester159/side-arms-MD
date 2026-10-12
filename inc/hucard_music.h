#pragma once
/* Return a source song ID, or -1 when the command is not a mapped music start.
 * Command meanings remain shared by Normal, Boss Rush and Before Christ. */
signed char hucard_music_track(unsigned char command);
