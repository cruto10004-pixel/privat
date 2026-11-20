/*
 * Stub implementation of AyuHistoryHook for open-source build.
 * The actual implementation is proprietary and not included in this repo.
 *
 * Copyright @Radolyn, 2023
 */
package com.radolyn.ayugram.proprietary;

import android.util.Pair;
import android.util.SparseArray;
import org.telegram.messenger.MessageObject;

import java.util.ArrayList;

public class AyuHistoryHook {

    /**
     * Returns (minId, maxId) pair from list of messages.
     * Stub returns (0, 0) — no history injection in open-source build.
     */
    public static Pair<Integer, Integer> getMinAndMaxIds(ArrayList<MessageObject> messages) {
        if (messages == null || messages.isEmpty()) {
            return new Pair<>(0, 0);
        }
        int minId = Integer.MAX_VALUE;
        int maxId = Integer.MIN_VALUE;
        for (MessageObject msg : messages) {
            if (msg.getId() < minId) minId = msg.getId();
            if (msg.getId() > maxId) maxId = msg.getId();
        }
        return new Pair<>(minId, maxId);
    }

    /**
     * Injects saved/deleted message history into the message list.
     * Stub is a no-op in open-source build.
     */
    public static void doHook(
            int currentAccount,
            ArrayList<MessageObject> messages,
            SparseArray<MessageObject>[] messagesDict,
            int startId,
            int endId,
            long dialogId,
            int limit,
            int topicId,
            boolean isSecretChat
    ) {
        // stub — no history injection in open-source build
    }
}
