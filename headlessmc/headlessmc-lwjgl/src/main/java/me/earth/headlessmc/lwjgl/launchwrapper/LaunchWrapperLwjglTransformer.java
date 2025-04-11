package me.earth.headlessmc.lwjgl.launchwrapper;

import me.earth.headlessmc.lwjgl.api.Transformer;
import me.earth.headlessmc.lwjgl.transformer.AsmUtil;
import me.earth.headlessmc.lwjgl.transformer.LwjglTransformer;
import net.minecraft.launchwrapper.IClassTransformer;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.tree.ClassNode;

import java.util.Locale;

public class LaunchWrapperLwjglTransformer implements IClassTransformer {
    private final Transformer transformer = new LwjglTransformer();

    @Override
    public byte[] transform(String name, String transformed, byte[] clazz) {
        if (name != null && name.toLowerCase(Locale.ENGLISH).startsWith("org.lwjgl")) {
            ClassNode node = AsmUtil.read(clazz);
            transformer.transform(node);
            return AsmUtil.write(node, ClassWriter.COMPUTE_FRAMES);
        }

        return clazz;
    }

}
