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
package net.famzangl.minecraft.minebot.build;

import java.util.LinkedList;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.BlockItemFilter;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSets;
import net.famzangl.minecraft.minebot.ai.task.AITask;
import net.famzangl.minecraft.minebot.ai.task.TaskOperations;
import net.famzangl.minecraft.minebot.ai.task.error.SelectTaskError;
import net.famzangl.minecraft.minebot.ai.task.move.HorizontalMoveTask;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumFacing;
import net.minecraft.util.MovementInput;

/**
 * This task lets you walk from one position to an other, adjacent position. In
 * contrast to the {@link HorizontalMoveTask}, it won't destroy blocks. It can
 * walk up by placing carpets on the floor and destroying them afterwards.
 * 
 * @author michael
 *
 */
public class WalkTowardsTask extends AITask {

	private static final BlockSet CARPETS = new BlockSet(
			Blocks.field_150404_cg);

	private static final BlockItemFilter CARPET = new BlockItemFilter(CARPETS);
	private final BlockPos fromPos;
	private final BlockPos nextPos;
	private final boolean placeCarpets;

	private AITask subTask;

	private final LinkedList<BlockPos> carpets = new LinkedList<BlockPos>();
	private boolean wasStandingOnDest;

	public WalkTowardsTask(BlockPos fromPos, BlockPos nextPos) {
		this(fromPos, nextPos, true);
	}
	
	public WalkTowardsTask(BlockPos fromPos, BlockPos nextPos, boolean placeCarpets) {
		this.fromPos = fromPos;
		this.nextPos = nextPos;
		this.placeCarpets = placeCarpets;
	}

	@Override
	public boolean isFinished(AIHelper h) {
		return subTask == null
				&& h.isStandingOn(nextPos.func_177958_n(), nextPos.func_177956_o(),
						nextPos.func_177952_p()) && carpets.isEmpty();
		/* && getUpperCarpetY(h) < 0 */
	}

	@Override
	public void runTick(AIHelper h, TaskOperations o) {
		if (subTask != null && subTask.isFinished(h)) {
			subTask = null;
		}
		if (subTask != null) {
			subTask.runTick(h, o);
		} else {
			final int carpetY = getUpperCarpetY(h);
			final double carpetBuildHeight = h.realBlockTopY(fromPos.func_177958_n(),
					Math.max(carpetY + 1, fromPos.func_177956_o()), fromPos.func_177952_p());
			final double destHeight = h.realBlockTopY(nextPos.func_177958_n(),
					nextPos.func_177956_o(), nextPos.func_177952_p());
			if (carpetBuildHeight < destHeight - 1 && placeCarpets) {
				System.out.println("Moving upwards. Carpets are at " + carpetY);
				final int floorY = Math.max(carpetY, fromPos.func_177956_o() - 1);
				BlockPos floor = new BlockPos(fromPos.func_177958_n(), floorY,
						fromPos.func_177952_p());
				h.faceBlock(floor);
				if (h.isFacingBlock(floor, EnumFacing.UP)) {
					if (h.selectCurrentItem(CARPET)) {
						h.overrideUseItem();
						carpets.add(new BlockPos(fromPos.func_177958_n(), floorY + 1,
								fromPos.func_177952_p()));
					} else {
						o.desync(new SelectTaskError(CARPET));
					}
				}
				final MovementInput i = new MovementInput();
				i.field_78901_c = true;
				h.overrideMovement(i);
			} else if ((h.isStandingOn(nextPos.func_177958_n(), nextPos.func_177956_o(),
					nextPos.func_177952_p()) || wasStandingOnDest)
					&& !carpets.isEmpty()) {
				// Destruct everything after arriving at dest. Then walk to dest
				// again.

				while (!carpets.isEmpty()) {
					// Clean up carpets we already "lost"
					final BlockPos last = carpets.getLast();
					if (BlockSets.AIR.isAt(h.getWorld(), last)) {
						carpets.removeLast();
					}
				}

				final int x = fromPos.func_177958_n() - nextPos.func_177958_n();
				final int z = fromPos.func_177958_n() - nextPos.func_177958_n();
				if (h.sneakFrom(nextPos, AIHelper.getDirectionForXZ(x, z))) {
					final BlockPos last = carpets.getLast();
					h.faceAndDestroy(last);
				}

				wasStandingOnDest = true;
			} else {
				h.walkTowards(nextPos.func_177958_n() + 0.5, nextPos.func_177952_p() + 0.5,
						carpetBuildHeight < destHeight - 0.5);
			}
		}
	}

	/**
	 * Gets the Y of the topmost carpet that was placed. -1 if there was none.
	 * 
	 * @param h
	 * @return
	 */
	private int getUpperCarpetY(AIHelper h) {
		int upperCarpet = -1;
		for (int y = BlockSets.AIR.unionWith(CARPETS).isAt(h.getWorld(), 
				fromPos) ? fromPos.func_177956_o() : fromPos.func_177956_o() + 1; y < nextPos
				.func_177956_o(); y++) {
			if (CARPETS.contains(h.getBlock(fromPos.func_177958_n(), y, fromPos.func_177952_p()))) {
				upperCarpet = y;
			} else {
				break;
			}
		}
		return upperCarpet;
	}

	@Override
	public String toString() {
		return "WalkTowardsTask [currentPos=" + fromPos + ", nextPos="
				+ nextPos + ", subTask=" + subTask + "]";
	}
}
