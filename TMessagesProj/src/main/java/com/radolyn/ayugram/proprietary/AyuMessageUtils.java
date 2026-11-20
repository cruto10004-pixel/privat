/*
 * Stub implementation of AyuMessageUtils for open-source build.
 * The actual implementation is proprietary and not included in this repo.
 *
 * Copyright @Radolyn, 2023
 */
package com.radolyn.ayugram.proprietary;

import com.radolyn.ayugram.database.entities.DeletedMessage;
import com.radolyn.ayugram.database.entities.EditedMessage;
import com.radolyn.ayugram.messages.AyuSavePreferences;
import org.telegram.tgnet.TLRPC;

public class AyuMessageUtils {

    // Called from AyuMessagesController: map(prefs, editedMessage) where editedMessage is EditedMessage
    public static void map(AyuSavePreferences prefs, EditedMessage revision) {
        // stub — no-op
    }

    // Called from AyuMessagesController: map(prefs, deletedMessage)
    public static void map(AyuSavePreferences prefs, DeletedMessage deletedMessage) {
        // stub — no-op
    }

    // Called from AyuMessageHistory: map(editedMessage, TL_message, currentAccount)
    public static void map(EditedMessage editedMessage, TLRPC.TL_message msg, int currentAccount) {
        // stub — no-op
    }

    // Called from AyuMessagesController: mapMedia(prefs, revision, copyMedia)
    public static void mapMedia(AyuSavePreferences prefs, EditedMessage revision, boolean copyMedia) {
        // stub — no-op
    }

    // Called from AyuMessagesController: mapMedia(prefs, deletedMessage, true)
    public static void mapMedia(AyuSavePreferences prefs, DeletedMessage deletedMessage, boolean copyMedia) {
        // stub — no-op
    }

    // Called from AyuMessageHistory: mapMedia(editedMessage, TL_message)
    public static void mapMedia(EditedMessage editedMessage, TLRPC.TL_message msg) {
        // stub — no-op
    }
}
