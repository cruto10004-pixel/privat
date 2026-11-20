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

public class AyuMessageUtils {

    /**
     * Maps AyuSavePreferences to EditedMessage entity.
     */
    public static void map(AyuSavePreferences prefs, EditedMessage revision) {
        // stub — no-op in open-source build
    }

    /**
     * Maps media data from AyuSavePreferences to EditedMessage entity.
     */
    public static void mapMedia(AyuSavePreferences prefs, EditedMessage revision, boolean copyMedia) {
        // stub — no-op in open-source build
    }

    /**
     * Maps AyuSavePreferences to DeletedMessage entity.
     */
    public static void map(AyuSavePreferences prefs, DeletedMessage deletedMessage) {
        // stub — no-op in open-source build
    }

    /**
     * Maps media data from AyuSavePreferences to DeletedMessage entity.
     */
    public static void mapMedia(AyuSavePreferences prefs, DeletedMessage deletedMessage, boolean copyMedia) {
        // stub — no-op in open-source build
    }
}
