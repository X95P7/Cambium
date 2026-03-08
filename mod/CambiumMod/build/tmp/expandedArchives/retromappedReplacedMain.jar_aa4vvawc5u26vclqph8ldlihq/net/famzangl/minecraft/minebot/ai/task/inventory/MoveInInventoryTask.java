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
import net.famzangl.minecraft.minebot.ai.task.AITask;
import net.famzangl.minecraft.minebot.ai.task.TaskOperations;
import net.famzangl.minecraft.minebot.ai.task.error.StringTaskError;
import net.minecraft.client.gui.inventory.GuiContainer;
import net.minecraft.inventory.Slot;

import org.apache.logging.log4j.Marker;
import org.apache.logging.log4j.MarkerManager;

/**
 * Move a given amount from one slot to an other, empty slot in the current open
 * container/inventory.
 * 
 * @author michael
 *
 */
public abstract class MoveInInventoryTask extends AITask {

	private static final Marker MARKER_MOVE = MarkerManager.getMarker("move");
	private boolean moveDone;

	private int delay;

	public static final int DELAY = 5;

	/**
	 * All 3 methods should return constant values.
	 * 
	 * @return
	 */
	protected abstract int getFromStack(AIHelper h);

	protected abstract int getToStack(AIHelper h);

	/**
	 * How many items should be moved. Mind that items may be put back (might be
	 * a problem on get-only containers)
	 * 
	 * @param currentCount
	 * 
	 * @return
	 */
	protected abstract int getMissingAmount(AIHelper h, int currentCount);

	/**
	 * If not all items could be moved, this is called.
	 * 
	 * @param missing
	 *            Missing item count.
	 */
	protected void missingItems(int missing) {

	}

	@Override
	public boolean isFinished(AIHelper h) {
		return moveDone;
	}

	@Override
	public void runTick(AIHelper h, TaskOperations o) {
		final GuiContainer screen = (GuiContainer) h.getMinecraft().field_71462_r;
		if (screen == null) {
			o.desync(new StringTaskError("Expected container to be open"));
			return;
		}
		if (delay > 0) {
			delay--;
		} else {
			int fromStack = getFromStack(h);
			int toStack = getToStack(h);
			if (fromStack < 0
					|| toStack < 0
					|| fromStack >= screen.field_147002_h.field_75153_a
							.size()
					|| toStack >= screen.field_147002_h.field_75153_a
							.size()) {
				LOGGER.error("Attempet to move : " + fromStack + " -> "
						+ toStack);
				o.desync(new StringTaskError("Invalid item move specification."));
				return;
			}
			Slot from = screen.field_147002_h.func_75139_a(fromStack);
			if (getSlotContentCount(from) <= 0) {
				o.desync(new StringTaskError("Nothing in source slot."));
				LOGGER.error(MARKER_MOVE, "Attempted to move from slot "
						+ fromStack + " but it was empty (" + from.field_75222_d
						+ ", " + from.func_75211_c() + ")");
				return;
			}

			Slot to = screen.field_147002_h.func_75139_a(toStack);
			int amount = getMissingAmount(h, getSlotContentCount(to));
			LOGGER.debug(MARKER_MOVE, "Move " + amount + " from " + fromStack
					+ " to " + toStack);

			int limit = Math.min(to.func_75219_a(), from.func_75211_c()
					.func_77976_d());
			int missing = Math.min(amount, limit - getSlotContentCount(to));

			while (getSlotContentCount(from) <= missing
					&& getSlotContentCount(from) > 0) {
				missing -= moveAll(h, from, to);
			}

			LOGGER.debug("Still missing (1): " + missing);
			if (getSlotContentCount(from) - getSlotContentCount(from) / 2 <= missing
					&& getSlotContentCount(from) > 0) {
				missing -= moveHalf(h, from, to);
			} else if (missing > 0 && getSlotContentCount(from) > 0) {
				missing -= moveStackPart(h, from, to, missing);
			} else if (missing > 0) {
				missingItems(missing);
			} else {
				moveDone = true;
			}
			delay = DELAY;
		}
	}

	private int moveAll(AIHelper h, Slot from, Slot to) {
		return moveStack(h, from, to, false);
	}

	private int moveHalf(AIHelper h, Slot from, Slot to) {
		return moveStack(h, from, to, true);
	}

	private int moveStack(AIHelper h, Slot from, Slot to,
			boolean rightclickOnStart) {
		int oldCount = getSlotContentCount(to);

		click(h, from.field_75222_d, rightclickOnStart ? 1 : 0);

		click(h, to.field_75222_d, 0);
		return getSlotContentCount(to) - oldCount;
	}

	private void click(AIHelper h, int slotNumber, int i) {
		System.out.println("Click on " + slotNumber + " using " + i);
		final GuiContainer screen = (GuiContainer) h.getMinecraft().field_71462_r;
		h.getMinecraft().field_71442_b.func_78753_a(
				screen.field_147002_h.field_75152_c, slotNumber, i, 0,
				h.getMinecraft().field_71439_g);
	}

	private int moveStackPart(AIHelper h, Slot from, Slot to, int count) {
		int oldCount = getSlotContentCount(to);

		click(h, from.field_75222_d, 0);
		for (int i = 0; i < count; i++) {
			click(h, to.field_75222_d, 1);
		}
		click(h, from.field_75222_d, 0);
		return getSlotContentCount(to) - oldCount;
	}

	protected int getSlotContentCount(Slot slot) {
		return slot.func_75216_d() ? slot.func_75211_c().field_77994_a : 0;
	}

	protected static int convertPlayerInventorySlot(int inventorySlot) {
		// Offset: 10 blocks.
		if (inventorySlot < 9) {
			return inventorySlot + 9 * 3;
		} else {
			return inventorySlot - 9;
		}
	}
}
