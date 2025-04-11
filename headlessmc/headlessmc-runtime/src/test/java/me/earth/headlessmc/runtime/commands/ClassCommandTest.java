package me.earth.headlessmc.runtime.commands;

import lombok.SneakyThrows;
import me.earth.headlessmc.api.command.CommandException;
import me.earth.headlessmc.runtime.RuntimeTest;
import me.earth.headlessmc.runtime.TestClass;
import me.earth.headlessmc.runtime.commands.reflection.ClassCommand;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

public class ClassCommandTest implements RuntimeTest {
    private final ClassCommand command = new ClassCommand(getRuntime());

    @Test
    @SneakyThrows
    public void testClassCommand() {
        assertThrows(CommandException.class,
                     () -> command.execute("class", "class"));
        assertThrows(CommandException.class,
                     () -> command.execute("class test", "class", "test"));

        command.ctx.getVm().set(null, 0);
        assertNull(command.ctx.getVm().get(0));
        command.execute("", "class", TestClass.class.getName(), "0");
        assertEquals(TestClass.class, command.ctx.getVm().get(0));

        command.execute("", "class", "int", "0", "-primitive");
        assertEquals(int.class, command.ctx.getVm().get(0));
    }

}
