/*
 * Stub implementation of EncryptionHelper for open-source build.
 * The actual implementation is proprietary and not included in this repo.
 */
package com.exteragram.messenger.boost.encryption;

import android.util.SparseIntArray;
import org.telegram.messenger.MessageObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class EncryptionHelper {

    public static final List<String> names = new ArrayList<>(Arrays.asList("None"));

    private static final BaseEncryptor STUB_ENCRYPTOR = new BaseEncryptor() {
        @Override
        public String getName() {
            return "None";
        }
    };

    public static boolean isEncrypted(String message) {
        return false;
    }

    public static boolean isEncrypted(MessageObject messageObject, Object extra) {
        return false;
    }

    public static BaseEncryptor getEncryptorBy(long dialogId) {
        return STUB_ENCRYPTOR;
    }

    public static int getEncryptorTypeFor(long dialogId) {
        return 0;
    }

    public static void setEncryptorTypeFor(long dialogId, int type) {
        // stub
    }

    public static void encryptMessage(String text, long dialogId, int encryptorType, EncryptCallback callback) {
        if (callback != null) {
            callback.onResult(text);
        }
    }

    public static String encryptMessage(String text, long dialogId, BaseEncryptor encryptor) {
        return text;
    }

    public static MessageObject decryptMessage(MessageObject messageObject) {
        return messageObject;
    }

    public static MessageObject decryptMessage(MessageObject messageObject, Object group) {
        return messageObject;
    }

    public interface EncryptCallback {
        void onResult(String message);
    }
}
