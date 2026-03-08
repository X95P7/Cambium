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
package net.famzangl.minecraft.minebot.ai.task.inventory;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.ItemFilter;
import net.famzangl.minecraft.minebot.ai.task.AITask;
import net.famzangl.minecraft.minebot.ai.task.SkipWhenSearchingPrefetch;
import net.famzangl.minecraft.minebot.ai.task.TaskOperations;
import net.famzangl.minecraft.minebot.ai.task.error.SelectTaskError;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraft.client.gui.inventory.GuiInventory;
import net.minecraft.client.multiplayer.PlayerControllerMP;
import net.minecraft.inventory.Slot;
import net.minecraft.item.ItemStack;
import net.minecraft.network.play.client.C16PacketClientStatus;

import org.apache.logging.log4j.Marker;
import org.apache.logging.log4j.MarkerManager;

/**
 * Gets the item on the hotbar out of the inventory. Currently only uses slot 5.
 * 
 * @author michael
 * 
 */
@SkipWhenSearchingPrefetch
public class GetOnHotBarTask extends AITask {
	private static final Marker MARKER_GET_ON_HOTBAR = MarkerManager.getMarker("get_on_hotbar");
	private final ItemFilter itemFiler;
	private boolean inventoryOpened;

	public GetOnHotBarTask(ItemFilter itemFiler) {
		super();
		this.itemFiler = itemFiler;
	}

	@Override
	public boolean isFinished(AIHelper h) {
		return h.canSelectItem(itemFiler)
				&& h.getMinecraft().field_71462_r == null;
	}

	@Override
	public void runTick(AIHelper h, TaskOperations o) {
		if (h.getMinecraft().field_71462_r instanceof GuiInventory) {
			final GuiInventory screen = (GuiInventory) h.getMinecraft().field_71462_r;
			for (int i = 9; i < 9 * 4; i++) {
				final Slot slot = screen.field_147002_h.func_75139_a(i);
				final ItemStack stack = slot.func_75211_c();
				if (slot == null || stack == null
						|| !slot.func_82869_a(h.getMinecraft().field_71439_g)
						|| !itemFiler.matches(stack)) {
					continue;
				}
				LOGGER.trace(MARKER_GET_ON_HOTBAR, "Swapping inventory slot " + i);
				swap(h, screen, i);
				h.getMinecraft().func_147108_a(null);
				break;
			}
		} else if (!inventoryOpened && h.hasItemInInvetory(itemFiler)) {
			h.getMinecraft()
					.func_147114_u()
					.func_147297_a(
							new C16PacketClientStatus(
									C16PacketClientStatus.EnumState.OPEN_INVENTORY_ACHIEVEMENT));
			h.getMinecraft().func_147108_a(
					new GuiInventory(h.getMinecraft().field_71439_g));
			inventoryOpened = true;
		} else {
			o.desync(new SelectTaskError(itemFiler));
		}
	}

	/**
	 * Swap a stack with Stack 5 on the hotbar.
	 * 
	 * @param h
	 * @param screen
	 * @param i
	 */
	private void swap(AIHelper h, GuiInventory screen, int i) {
		final PlayerControllerMP playerController = h.getMinecraft().field_71442_b;
		final int windowId = screen.field_147002_h.field_75152_c;
		final EntityPlayerSP player = h.getMinecraft().field_71439_g;
		playerController.func_78753_a(windowId, i, 0, 0, player);
		playerController.func_78753_a(windowId, 35 + 5, 0, 0, player);
		playerController.func_78753_a(windowId, i, 0, 0, player);
	}

}
