package com.radolyn.ayugram.proprietary;

import com.radolyn.ayugram.messages.AyuSavePreferences;
import com.radolyn.ayugram.database.entities.AyuMessageBase;
import com.radolyn.ayugram.database.entities.EditedMessage;
import com.radolyn.ayugram.database.entities.DeletedMessage;
import org.telegram.tgnet.TLRPC;

public class AyuMessageUtils {

    public static void map(AyuSavePreferences prefs, AyuMessageBase entity) {
        // stub
    }

    public static void map(AyuSavePreferences prefs, EditedMessage revision) {
        // stub
    }

    public static void map(AyuSavePreferences prefs, DeletedMessage deletedMessage) {
        // stub
    }

    public static void map(EditedMessage editedMessage, TLRPC.Message msg, int currentAccount) {
        if (msg == null || editedMessage == null) return;
        editedMessage.messageId = msg.id;
        editedMessage.text = msg.message;
        editedMessage.date = msg.edit_date != 0 ? msg.edit_date : msg.date;
        if (msg.peer_id != null) {
            editedMessage.peerId = msg.peer_id.channel_id != 0 ? msg.peer_id.channel_id
                    : msg.peer_id.chat_id != 0 ? msg.peer_id.chat_id
                    : msg.peer_id.user_id;
        }
    }

    public static void map(EditedMessage editedMessage, TLRPC.TL_message msg, int currentAccount) {
        map(editedMessage, (TLRPC.Message) msg, currentAccount);
    }

    public static void mapMedia(EditedMessage editedMessage, TLRPC.TL_message msg) {
        // stub
    }

    public static void mapMedia(AyuSavePreferences prefs, AyuMessageBase entity, boolean copyFile) {
        // stub
    }

    public static void mapMedia(AyuSavePreferences prefs, EditedMessage revision, boolean copyMedia) {
        // stub
    }

    public static void mapMedia(AyuSavePreferences prefs, DeletedMessage deletedMessage, boolean copyMedia) {
        // stub
    }

    public static void mapMedia(EditedMessage editedMessage, TLRPC.Message msg) {
        // stub
    }
}
