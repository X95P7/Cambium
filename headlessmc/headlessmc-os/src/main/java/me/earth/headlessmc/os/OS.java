package me.earth.headlessmc.os;

import lombok.Data;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import me.earth.headlessmc.api.HasName;

/**
 * Represents an Operating System.
 */
@Data
@RequiredArgsConstructor
public class OS implements HasName {
    private final String name;
    private final Type type;
    private final String version;
    private final String architecture;
    private final boolean b64;

    // here for legacy reasons
    public OS(String name, Type type, String version, boolean b64) {
        this(name, type, version, b64 ? "x64" : "x86", b64);
    }

    public boolean is64bit() {
        return b64;
    }

    @Getter
    @RequiredArgsConstructor
    public enum Type implements HasName {
        WINDOWS("windows"),
        LINUX("linux"),
        OSX("osx"),
        UNKNOWN("unknown");

        private final String name;
    }

}
