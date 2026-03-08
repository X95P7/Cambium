package net.famzangl.minecraft.minebot.ai.scripting;

import javax.script.ScriptEngine;
import javax.script.ScriptException;

import net.famzangl.minecraft.minebot.ai.net.MinebotNetHandler.PersistentChat;

public class ChatMessage {

	public final Object time;
	public final String text;
	public final String textFormatted;
	public final boolean isChat;

	public ChatMessage(PersistentChat m, ScriptEngine engine)
			throws ScriptException {
		time = engine.eval("new Date(" + m.getTime() + ")");
		text = m.getMessage().func_150260_c();
		textFormatted = m.getMessage().func_150254_d();
		isChat = m.isChat();
	}

	@Override
	public String toString() {
		return "ChatMessage [text=" + text + "]";
	}
	
}
