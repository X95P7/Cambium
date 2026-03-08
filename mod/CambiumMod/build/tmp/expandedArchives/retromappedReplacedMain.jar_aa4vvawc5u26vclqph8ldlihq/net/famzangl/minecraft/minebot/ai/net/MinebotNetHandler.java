/*******************************************************************************
 * This file is part of Minebot.
 *
 * Minebot is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Minebot is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Minebot.  If not, see <http://www.gnu.org/licenses/>.
 *******************************************************************************/
package net.famzangl.minecraft.minebot.ai.net;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CopyOnWriteArrayList;

import net.famzangl.minecraft.minebot.ai.AIController;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.utils.PrivateFieldUtils;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiScreen;
import net.minecraft.client.network.NetHandlerPlayClient;
import net.minecraft.entity.Entity;
import net.minecraft.network.NetworkManager;
import net.minecraft.network.Packet;
import net.minecraft.network.play.INetHandlerPlayClient;
import net.minecraft.network.play.client.C01PacketChatMessage;
import net.minecraft.network.play.client.C14PacketTabComplete;
import net.minecraft.network.play.server.S02PacketChat;
import net.minecraft.network.play.server.S08PacketPlayerPosLook;
import net.minecraft.network.play.server.S21PacketChunkData;
import net.minecraft.network.play.server.S22PacketMultiBlockChange;
import net.minecraft.network.play.server.S22PacketMultiBlockChange.BlockUpdateData;
import net.minecraft.network.play.server.S23PacketBlockChange;
import net.minecraft.network.play.server.S24PacketBlockAction;
import net.minecraft.network.play.server.S26PacketMapChunkBulk;
import net.minecraft.network.play.server.S28PacketEffect;
import net.minecraft.network.play.server.S29PacketSoundEffect;
import net.minecraft.network.play.server.S2APacketParticles;
import net.minecraft.network.play.server.S3APacketTabComplete;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumParticleTypes;
import net.minecraft.util.IChatComponent;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.Marker;
import org.apache.logging.log4j.MarkerManager;

import com.mojang.authlib.GameProfile;

import net.minecraft.network.play.server.S22PacketMultiBlockChange.BlockUpdateData;
public class MinebotNetHandler extends NetHandlerPlayClient implements
		NetworkHelper {
	private static final Marker MARKER_CHAT = MarkerManager
			.getMarker("chat");
	private static final Marker MARKER_FISH = MarkerManager
			.getMarker("fish");
	private static final Marker MARKER_COMPLETE = MarkerManager
			.getMarker("complete");
	private static final Marker MARKER_POS = MarkerManager
			.getMarker("pos");
	private static final Logger LOGGER = LogManager.getLogger(MinebotNetHandler.class);

	public static class PersistentChat {

		private final IChatComponent message;

		private final boolean chat;

		private final long time = System.currentTimeMillis();

		public PersistentChat(S02PacketChat packetIn) {
			chat = packetIn.func_148916_d();
			message = packetIn.func_148915_c();
		}

		public IChatComponent getMessage() {
			return message;
		}

		public boolean isChat() {
			return chat;
		}

		public long getTime() {
			return time;
		}

		@Override
		public String toString() {
			return "PersistentChat [message=" + message + ", chat=" + chat
					+ "]";
		}

	}

	private static final double MAX_FISH_DISTANCE = 10;

	private final ConcurrentLinkedQueue<BlockPos> foundFishPositions = new ConcurrentLinkedQueue<BlockPos>();

	private final CopyOnWriteArrayList<ChunkListener> listeners = new CopyOnWriteArrayList<ChunkListener>();

	private String lastSendTabComplete;

	private final ArrayList<PersistentChat> chatMessages = new ArrayList<PersistentChat>();
	private Minecraft mcIn;

	public MinebotNetHandler(Minecraft mcIn, GuiScreen p_i46300_2_,
			NetworkManager p_i46300_3_, GameProfile p_i46300_4_) {
		super(mcIn, p_i46300_2_, p_i46300_3_, p_i46300_4_);
		this.mcIn = mcIn;
	}

	@Override
	public void func_147297_a(Packet p_147297_1_) {
		if (p_147297_1_ instanceof C01PacketChatMessage) {
			C01PacketChatMessage message = (C01PacketChatMessage) p_147297_1_;
			// Intercept chat message.
			String m = message.func_149439_c();
			if (m.startsWith("/")) {
				if (AIChatController.getRegistry().interceptCommand(m)) {
					return;
				}
			}
		} else if (p_147297_1_ instanceof C14PacketTabComplete) {
			C14PacketTabComplete complete = (C14PacketTabComplete) p_147297_1_;
			String m = complete.func_149419_c();
			if (m.startsWith("/") && m.indexOf(" ") >= 0) {
				if (AIChatController.getRegistry().interceptTab(m, this)) {
					return;
				}
			}
			lastSendTabComplete = m;
		}
		super.func_147297_a(p_147297_1_);
	}

	@Override
	public void func_147274_a(S3APacketTabComplete packetIn) {
		if (lastSendTabComplete != null && lastSendTabComplete.startsWith("/")
				&& !lastSendTabComplete.contains(" ")) {
			String[] newStrings = AIChatController.getRegistry()
					.fillTabComplete(this, packetIn.func_149630_c(),
							lastSendTabComplete);
			packetIn = new S3APacketTabComplete(newStrings);
			lastSendTabComplete = null;
		}
		super.func_147274_a(packetIn);
	}

	public static NetworkHelper inject(AIController aiController,
			NetworkManager manager, INetHandlerPlayClient oldHandler) {
		NetHandlerPlayClient netHandler = (NetHandlerPlayClient) oldHandler;
		if (netHandler != null && netHandler instanceof NetHandlerPlayClient) {

			if (!(netHandler instanceof MinebotNetHandler)) {
				GuiScreen screen = PrivateFieldUtils.getFieldValue(netHandler,
						NetHandlerPlayClient.class, GuiScreen.class);
				MinebotNetHandler handler = new MinebotNetHandler(
						aiController.getMinecraft(), screen,
						netHandler.func_147298_b(),
						netHandler.func_175105_e());
				netHandler.func_147298_b().func_150719_a(handler);
				LOGGER.info("Minebot network handler injected.");
				return handler;
			} else {
				return (NetworkHelper) netHandler;
			}
		}
		return null;
	}

	@Override
	public void func_147289_a(S2APacketParticles packetIn) {
		// For detecting fishing rod events.
		if (packetIn.func_179749_a() == EnumParticleTypes.WATER_SPLASH) {
			if (packetIn.func_149222_k() > 0) {
				double x = packetIn.func_149220_d();
				double y = packetIn.func_149226_e();
				double z = packetIn.func_149225_f();
				LOGGER.trace(MARKER_FISH, "fish particle (?) at " + new BlockPos(x, y, z));
				// foundFishPositions.add(new BlockPos(x, y, z));
				// System.out.println("NetHandler: fish at " + new BlockPos(x,
				// y, z) + ", packet: " +
				// Arrays.toString(packetIn.getParticleArgs()) + "; " +
				// packetIn.getParticleCount()+ "; " + packetIn.getXOffset()+
				// "; " + packetIn.getYOffset()+ "; " + packetIn.getZOffset());
			}
		}
		super.func_147289_a(packetIn);
	}

	@Override
	public void func_147277_a(S28PacketEffect packetIn) {
		super.func_147277_a(packetIn);
	}

	@Override
	public void func_147255_a(S29PacketSoundEffect packetIn) {
		String name = packetIn.func_149212_c();
		if ("random.splash".equals(name)) {
			double x = packetIn.func_149207_d();
			double y = packetIn.func_149211_e();
			double z = packetIn.func_149210_f();
			foundFishPositions.add(new BlockPos(x, y, z));
			LOGGER.trace(MARKER_FISH, "fish at " + new BlockPos(x, y, z));
		}
		super.func_147255_a(packetIn);
	}

	public boolean fishIsCaptured(Entity expectedPos) {
		while (true) {
			BlockPos next = foundFishPositions.poll();
			if (next == null) {
				return false;
			} else if (expectedPos.func_70011_f(next.func_177958_n() + 0.5,
					next.func_177956_o() + 0.5, next.func_177952_p() + 0.5) < MAX_FISH_DISTANCE) {
				LOGGER.trace(MARKER_FISH, "found fish for " + expectedPos + ": " + next);
				return true;
			} else {
				LOGGER.trace(MARKER_FISH, "Found a fish bite at " + next
						+ " but fishing at " + expectedPos + ".");
			}
		}
	}

	public void resetFishState() {
		LOGGER.trace(MARKER_FISH, "reset");
		foundFishPositions.clear();
	}

	@Override
	public void func_147263_a(S21PacketChunkData packetIn) {
		int x = packetIn.func_149273_e();
		int z = packetIn.func_149271_f();
		fireChunkChange(x, z);
		super.func_147263_a(packetIn);
	}

	@Override
	public void func_147269_a(S26PacketMapChunkBulk packetIn) {
		for (int i = 0; i < packetIn.func_149254_d(); ++i) {
			int x = packetIn.func_149255_a(i);
			int y = packetIn.func_149255_a(i);
			fireChunkChange(x, y);
		}
		super.func_147269_a(packetIn);
	}

	@Override
	public void func_147234_a(S23PacketBlockChange packetIn) {
		blockChange(packetIn.func_179827_b());
		super.func_147234_a(packetIn);
	}

	@Override
	public void func_147261_a(S24PacketBlockAction packetIn) {
		blockChange(packetIn.func_179825_a());
		super.func_147261_a(packetIn);
	}
	
	@Override
	public void func_147287_a(S22PacketMultiBlockChange packetIn) {
		for (BlockUpdateData b : packetIn.func_179844_a()) {
			blockChange(b.func_180090_a());
		}
		super.func_147287_a(packetIn);
	}

	private void blockChange(BlockPos pos) {
		int chunkPosX = pos.func_177958_n() >> 4;
		int chunkPosZ = pos.func_177952_p() >> 4;
		fireChunkChange(chunkPosX, chunkPosZ);
	}

	private void fireChunkChange(int chunkPosX, int chunkPosZ) {
		for (ChunkListener l : listeners) {
			l.chunkChanged(chunkPosX, chunkPosZ);
		}
	}

	@Override
	public void addChunkChangeListener(ChunkListener l) {
		listeners.add(l);
	}

	@Override
	public void removeChunkChangeListener(ChunkListener l) {
		listeners.remove(l);
	}

	@Override
	public void func_147251_a(S02PacketChat packetIn) {
		if (mcIn.func_152345_ab()) {
			LOGGER.trace(MARKER_CHAT, "Received chat package: " + packetIn.hashCode() + ": " + packetIn.func_148915_c());
			chatMessages.add(new PersistentChat(packetIn));
		} // else: super passes it on to mc thread.
		super.func_147251_a(packetIn);
	}

	public List<PersistentChat> getChatMessages() {
		return Collections.unmodifiableList(chatMessages);
	}
	
	@Override
	public void func_147258_a(S08PacketPlayerPosLook packetIn) {
		LOGGER.trace(MARKER_POS, "Forced move to: " + packetIn.func_148932_c() + "," + packetIn.func_148933_e());
		super.func_147258_a(packetIn);
	}
}
