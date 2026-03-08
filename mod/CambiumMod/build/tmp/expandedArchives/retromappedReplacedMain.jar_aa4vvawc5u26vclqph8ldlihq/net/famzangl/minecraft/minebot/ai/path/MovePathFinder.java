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
package net.famzangl.minecraft.minebot.ai.path;

import java.util.LinkedList;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.BlockItemFilter;
import net.famzangl.minecraft.minebot.ai.PathFinderField;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSets;
import net.famzangl.minecraft.minebot.ai.path.world.Pos;
import net.famzangl.minecraft.minebot.ai.path.world.WorldData;
import net.famzangl.minecraft.minebot.ai.task.AITask;
import net.famzangl.minecraft.minebot.ai.task.move.AlignToGridTask;
import net.famzangl.minecraft.minebot.ai.task.move.DownwardsMoveTask;
import net.famzangl.minecraft.minebot.ai.task.move.HorizontalMoveTask;
import net.famzangl.minecraft.minebot.ai.task.move.JumpMoveTask;
import net.famzangl.minecraft.minebot.ai.task.move.UpwardsMoveTask;
import net.famzangl.minecraft.minebot.ai.task.move.WalkTowardsTask;
import net.famzangl.minecraft.minebot.settings.MinebotSettings;
import net.famzangl.minecraft.minebot.settings.MinebotSettingsRoot;
import net.famzangl.minecraft.minebot.settings.PathfindingSetting;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumFacing;

/**
 * A pathfinder that lets you move around a minecraft world.
 * <p>
 * This pathfinder uses several fields to check if a block may be walked
 * through.
 * 
 * @author Michael Zangl
 * 
 */
public class MovePathFinder extends PathFinderField {
	/**
	 * Blocks that are destructable faster.
	 */
	protected final static BlockSet fastDestructableBlocks = new BlockSet(
			Blocks.field_150346_d, Blocks.field_150351_n, Blocks.field_150354_m, Blocks.field_150322_A);

	/**
	 * Blocks we should not dig through, e.g. because we cannot handle them
	 * correctly.
	 */
	protected static final BlockSet defaultForbiddenBlocks = new BlockSet(
			Blocks.field_150357_h, Blocks.field_150434_aF, Blocks.field_150343_Z,
			Blocks.field_180384_M, Blocks.field_150332_K);

	/**
	 * The AI helper
	 */
	protected AIHelper helper;
	/**
	 * The local world we do path finding on. This may already represent the
	 * expected world state in the future.
	 */
	protected WorldData world;

	/**
	 * The minebot settings used.
	 */
	protected PathfindingSetting pathSettings;
	protected MinebotSettingsRoot settings;

	/**
	 * The blocks we use when building upwards.
	 */
	protected BlockSet upwardsBuildBlocks;

	/**
	 * This list can be changed. Only blocks of this type are walked to.
	 */
	protected BlockSet allowedGroundBlocks;
	/**
	 * Those ground blocks are the blocks we allow to 'stand' on after a upwards
	 * move.
	 */
	protected BlockSet allowedGroundForUpwardsBlocks;

	/**
	 * Blocks we allow the feet to walk through.
	 */
	protected BlockSet footAllowedBlocks;
	/**
	 * Blocks we allow the head to walk through.
	 */
	protected BlockSet headAllowedBlocks;

	protected BlockSet shortFootBlocks = BlockSets.FEET_CAN_WALK_THROUGH;
	protected BlockSet shortHeadBlocks = BlockSets.HEAD_CAN_WALK_TRHOUGH;

	protected PathfindingSetting setting;

	// /**
	// * Current forbidden block settings. Just FYI, never used by this
	// * pathfinder.
	// */
	// protected final BlockSet forbiddenBlocks;
	private TaskReceiver receiver;

	private volatile BlockPos currentTarget;

	public MovePathFinder() {
		super();
		settings = MinebotSettings.getSettings();
		pathSettings = loadSettings(settings);

		upwardsBuildBlocks = pathSettings.getUpwardsBuildBlocks();

		allowedGroundBlocks = pathSettings.getAllowedGround();
		allowedGroundForUpwardsBlocks = pathSettings
				.getAllowedGroundWhenUpwards();
		footAllowedBlocks = pathSettings.getFootWalkThrough();
		headAllowedBlocks = pathSettings.getHeadWalkThrough();

		// getBlocks("upwards_place_block",
		// defaultUpwardsBlocks);
		// forbiddenBlocks = settings.getBlocks("blacklisted_blocks",
		// defaultForbiddenBlocks);
		//
		// footAllowedBlocks = footAllowedBlocks.intersectWith(forbiddenBlocks
		// .invert());
		// headAllowedBlocks = headAllowedBlocks.intersectWith(forbiddenBlocks
		// .invert());
	}

	protected PathfindingSetting loadSettings(MinebotSettingsRoot settingsRoot) {
		return settingsRoot.getPathfinding().getDestructivePathfinder();
	}

	@Override
	protected final boolean searchSomethingAround(int cx, int cy, int cz) {
		throw new UnsupportedOperationException("Direct call not supported.");
	}

	protected void addTask(AITask task) {
		receiver.addTask(task);
	}

	public final boolean searchSomethingAround(BlockPos playerPosition,
			AIHelper helper, WorldData world, TaskReceiver receiver) {
		currentTarget = null;
		this.helper = helper;
		this.world = world;
		this.receiver = receiver;
		return runSearch(playerPosition);
	}

	/**
	 * 
	 * @param playerPosition
	 * @return <code>false</code> When pathfinding should be given more time.
	 */
	protected boolean runSearch(BlockPos playerPosition) {
		return super.searchSomethingAround(playerPosition.func_177958_n(),
				playerPosition.func_177956_o(), playerPosition.func_177952_p());
	}

	@Override
	protected int getNeighbour(int currentNode, int cx, int cy, int cz) {
		final int res = super.getNeighbour(currentNode, cx, cy, cz);
		if (res > 0 && !isSafeToTravel(currentNode, cx, cy, cz)) {
			return -1;
		}
		return res;
	}

	protected boolean isSafeToTravel(int currentNode, int cx, int cy, int cz) {
		return BlockSets.safeSideAround(world, cx, cy + 1, cz)
				&& isAllowedPosition(cx, cy, cz)
				&& BlockSets.safeSideAround(world, cx, cy, cz)
				&& checkHeadBlock(currentNode, cx, cy, cz)
				&& checkGroundBlock(currentNode, cx, cy, cz);
	}

	/**
	 * Are we allowed to travel there, only looking at the blocks that we need.
	 * 
	 * @param cx
	 * @param cy
	 * @param cz
	 * @return
	 */
	private boolean isAllowedPosition(int cx, int cy, int cz) {
		return footAllowedBlocks.isAt(world, cx, cy, cz)
				&& headAllowedBlocks.isAt(world, cx, cy + 1, cz);
	}

	protected boolean checkGroundBlock(int currentNode, int cx, int cy, int cz) {
		if (getY(currentNode) < cy) {
			return allowedGroundForUpwardsBlocks.isAt(world, cx, cy - 1, cz);
		} else {
			return allowedGroundBlocks.isAt(world, cx, cy - 1, cz);
		}
	}

	private boolean checkHeadBlock(int currentNode, int cx, int cy, int cz) {
		if (getY(currentNode) > cy) {
			if (getX(currentNode) != cx || getZ(currentNode) != cz) {
				return BlockSets.SAFE_CEILING.isAt(world, cx, cy + 3, cz)
						&& BlockSets.HEAD_CAN_WALK_TRHOUGH.isAt(world, cx,
								cy + 2, cz);
			} else if (BlockSets.FALLING.isAt(world, cx, cy + 2, cz)) {
				// moving down, so ignoring sand, gravel.
				return true;
			}
		}
		return BlockSets.SAFE_CEILING.isAt(world, cx, cy + 2, cz);
	}

	@Override
	protected void noPathFound() {
		super.noPathFound();
	}

	@Override
	protected void foundPath(LinkedList<BlockPos> path) {
		super.foundPath(path);
		BlockPos currentPos = path.removeFirst();
		addTask(new AlignToGridTask(currentPos.func_177958_n(), currentPos.func_177956_o(),
				currentPos.func_177952_p()));
		while (!path.isEmpty()) {
			BlockPos nextPos = path.removeFirst();
			EnumFacing moveDirection = direction(currentPos, nextPos);
			int stepsAdded = 0;
			while (path.peekFirst() != null
					&& isAreaClear(currentPos, path.peekFirst())
					&& stepsAdded < 40) {
				nextPos = path.removeFirst();
				stepsAdded++;
			}
			final BlockPos peeked = path.peekFirst();
			if (stepsAdded > 0) {
				addHorizontalFastMove(currentPos, nextPos);
			} else if (moveDirection == EnumFacing.UP && peeked != null
					&& nextPos.func_177973_b(peeked).func_177956_o() == 0) {
				addJumpMoveTask(currentPos, peeked);
				nextPos = peeked;
				path.removeFirst();
			} else if (nextPos.func_177956_o() > currentPos.func_177956_o()
					&& nextPos.func_177958_n() == currentPos.func_177958_n()
					&& nextPos.func_177952_p() == currentPos.func_177952_p()) {
				addTask(new UpwardsMoveTask(nextPos, new BlockItemFilter(
						upwardsBuildBlocks)));
			} else if (nextPos.func_177956_o() > currentPos.func_177956_o()) {
				addJumpMoveTask(currentPos, nextPos);
			} else if (nextPos.func_177956_o() < currentPos.func_177956_o()
					&& nextPos.func_177958_n() == currentPos.func_177958_n()
					&& nextPos.func_177952_p() == currentPos.func_177952_p()) {
				addTask(new DownwardsMoveTask(nextPos));
			} else {
				addTask(new HorizontalMoveTask(nextPos));
			}
			currentPos = nextPos;
		}
		currentTarget = currentPos;
		addTasksForTarget(currentPos);
	}

	private void addJumpMoveTask(BlockPos nextPos, final BlockPos peeked) {
		addTask(new JumpMoveTask(peeked, nextPos.func_177958_n(), nextPos.func_177952_p()));
	}

	private void addHorizontalFastMove(BlockPos currentPos, BlockPos nextPos) {
		System.out.println("Shortcut from " + currentPos + " to "
				+ nextPos);
		addTask(new WalkTowardsTask(nextPos.func_177958_n(), nextPos.func_177952_p(),
				currentPos));
	}

	/**
	 * Could we take a shortcut without any objects in the way.
	 * 
	 * @param pos1
	 * @param pos2
	 * @return
	 */
	private boolean isAreaClear(BlockPos pos1, BlockPos pos2) {
		if (pos1.func_177956_o() != pos2.func_177956_o()) {
			return false;
		}
		BlockPos min = Pos.minPos(pos1, pos2);
		BlockPos max = Pos.maxPos(pos1, pos2);
		int y = pos1.func_177956_o();
		for (int x = min.func_177958_n(); x <= max.func_177958_n(); x++) {
			for (int z = min.func_177952_p(); z <= max.func_177952_p(); z++) {
				if (!BlockSets.SAFE_GROUND.isAt(world, x, y - 1, z)
						|| !BlockSets.SAFE_CEILING.isAt(world, x, y + 2, z)
						|| !BlockSets.FEET_CAN_WALK_THROUGH
								.isAt(world, x, y, z)
						|| !BlockSets.HEAD_CAN_WALK_TRHOUGH.isAt(world, x,
								y + 1, z)) {
					return false;
				}
			}
		}
		return true;
	}

	private EnumFacing direction(BlockPos currentPos, final BlockPos nextPos) {
		BlockPos delta = nextPos.func_177973_b(currentPos);
		if (delta.func_177956_o() != 0 && (delta.func_177958_n() != 0 || delta.func_177952_p() != 0)) {
			delta = new BlockPos(delta.func_177958_n(), 0, delta.func_177952_p());
		}
		return AIHelper.getDirectionFor(delta);
	}

	protected void addTasksForTarget(BlockPos currentPos) {
	}

	@Override
	protected int distanceFor(int from, int to) {
		int distance = 1;
		int toX = getX(to);
		int toY = getY(to);
		int toZ = getZ(to);
		int fromY = getY(from);
		if (fromY > toY && (toX != getX(from) || toY != getY(from))) {
			// sideward down
			distance += materialDistance(toX, toY + 2, toZ, false);
			distance += materialDistance(toX, toY + 1, toZ, false);
			distance += materialDistance(toX, toY, toZ, true);
			distance += 1;
		} else if (fromY > toY && (toX != getX(from) || toY != getY(from))) {
			// sideward up
			distance += materialDistance(getX(from), toY + 1, getZ(from), false);
			distance += materialDistance(toX, toY + 1, toZ, false);
			distance += materialDistance(toX, toY, toZ, true);
			distance += 1;
		} else {
			if (fromY >= toY) {
				distance += materialDistance(toX, toY, toZ, true);
			} else {
				distance += 2;
			}
			if (fromY <= toY) {
				distance += materialDistance(toX, toY + 1, toZ, false);
			} else {
				distance += 2;
			}
		}
		return distance;
	}

	protected int materialDistance(int x, int y, int z, boolean asFloor) {
		if (asFloor && shortFootBlocks.isAt(world, x, y, z) || !asFloor
				&& shortHeadBlocks.isAt(world, x, y, z)) {
			return 0;
		} else if (fastDestructableBlocks.isAt(world, x, y, z)) {
			// fast breaking gives bonus.
			return 1;
		} else {
			return 2;
		}
	}

	public BlockPos getCurrentTarget() {
		return currentTarget;
	}

}
