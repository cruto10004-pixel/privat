/*
 * Stub implementation of BaseEncryptor for open-source build.
 * The actual implementation is proprietary and not included in this repo.
 */
package com.exteragram.messenger.boost.encryption;

public abstract class BaseEncryptor {

    public abstract String getName();

    public String encrypt(String text) {
        return text;
    }

    public String decrypt(String text) {
        return text;
    }
}
