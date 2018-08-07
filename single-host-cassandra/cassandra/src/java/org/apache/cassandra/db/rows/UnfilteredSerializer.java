/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.cassandra.db.rows;

import java.io.IOException;

import com.google.common.collect.Collections2;

import org.apache.cassandra.config.ColumnDefinition;
import org.apache.cassandra.db.*;
import org.apache.cassandra.io.util.DataInputPlus;
import org.apache.cassandra.io.util.DataOutputPlus;

/**
 * Serialize/deserialize a single Unfiltered (both on-wire and on-disk).
 * <p>
 *
 * The encoded format for an unfiltered is {@code <flags>(<row>|<marker>)} where:
 * <ul>
 *   <li>
 *     {@code <flags>} is a byte (or two) whose bits are flags used by the rest
 *     of the serialization. Each flag is defined/explained below as the
 *     "Unfiltered flags" constants. One of those flags is an extension flag,
 *     and if present, indicates the presence of a 2ndbyte that contains more
 *     flags. If the extension is not set, defaults are assumed for the flags
 *     of that 2nd byte.
 *   </li>
 *   <li>
 *     {@code <row>} is
 *        {@code <clustering><sizes>[<pkliveness>][<deletion>][<columns>]<columns_data>}
 *     where:
 *     <ul>
 *       <li>{@code <clustering>} is the row clustering as serialized by
 *           {@link Clustering.serializer} (note that static row are an
 *           exception and don't have this). </li>
 *       <li>{@code <sizes>} are the sizes of the whole unfiltered on disk and
 *           of the previous unfiltered. This is only present for sstables and
 *           is used to efficiently skip rows (both forward and backward).</li>
 *       <li>{@code <pkliveness>} is the row primary key liveness infos, and it
 *           contains the timestamp, ttl and local deletion time of that info,
 *           though some/all of those can be absent based on the flags. </li>
 *       <li>{@code deletion} is the row deletion. It's presence is determined
 *           by the flags and if present, it conists of both the deletion
 *           timestamp and local deletion time.</li>
 *       <li>{@code <columns>} are the columns present in the row  encoded by
 *           {@link Columns.serializer#serializeSubset}. It is absent if the row
 *           contains all the columns of the {@code SerializationHeader} (which
 *           is then indicated by a flag). </li>
 *       <li>{@code <columns_data>} is the data for each of the column present
 *           in the row. The encoding of each data depends on whether the data
 *           is for a simple or complex column:
 *           <ul>
 *              <li>Simple columns are simply encoded as one {@code <cell>}</li>
 *              <li>Complex columns are encoded as {@code [<delTime>]<n><cell1>...<celln>}
 *                  where {@code <delTime>} is the deletion for this complex
 *                  column (if flags indicates its presence), {@code <n>} is the
 *                  vint encoded value of n, i.e. {@code <celln>}'s 1-based
 *                  inde and {@code <celli>} are the {@code <cell>} for this
 *                  complex column</li>
 *           </ul>
 *       </li>
 *     </ul>
 *   </li>
 *   <li>
 *     {@code <marker>} is {@code <bound><deletion>} where {@code <bound>} is
 *     the marker bound as serialized by {@link ClusteringBoundOrBoundary.serializer}
 *     and {@code <deletion>} is the marker deletion time.
 *   </li>
 * </ul>
 * <p>
 * The serialization of a {@code <cell>} is defined by {@link Cell.Serializer}.
 */
public class UnfilteredSerializer
{
    public static final UnfilteredSerializer serializer = new UnfilteredSerializer();

    /*
     * Unfiltered flags constants.
     */
    private final static int END_OF_PARTITION     = 0x01; // Signal the end of the partition. Nothing follows a <flags> field with that flag.
    private final static int IS_MARKER            = 0x02; // Whether the encoded unfiltered is a marker or a row. All following markers applies only to rows.
    private final static int HAS_TIMESTAMP        = 0x04; // Whether the encoded row has a timestamp (i.e. if row.partitionKeyLivenessInfo().hasTimestamp() == true).
    private final static int HAS_TTL              = 0x08; // Whether the encoded row has some expiration info (i.e. if row.partitionKeyLivenessInfo().hasTTL() == true).
    private final static int HAS_DELETION         = 0x10; // Whether the encoded row has some deletion info.
    private final static int HAS_ALL_COLUMNS      = 0x20; // Whether the encoded row has all of the columns from the header present.
    private final static int HAS_COMPLEX_DELETION = 0x40; // Whether the encoded row has some complex deletion for at least one of its columns.
    private final static int EXTENSION_FLAG       = 0x80; // If present, another byte is read containing the "extended flags" above.

    /*
     * Extended flags
     */
    private final static int IS_STATIC               = 0x01; // Whether the encoded row is a static. If there is no extended flag, the row is assumed not static.
    private final static int HAS_SHADOWABLE_DELETION = 0x02; // Whether the row deletion is shadowable. If there is no extended flag (or no row deletion), the deletion is assumed not shadowable.

    public void serialize(Unfiltered unfiltered, SerializationHeader header, DataOutputPlus out, int version)
    throws IOException
    {
        assert !header.isForSSTable();
        serialize(unfiltered, header, out, 0, version);
    }

    public void serialize(Unfiltered unfiltered, SerializationHeader header, DataOutputPlus out, long previousUnfilteredSize, int version)
    throws IOException
    {
        if (unfiltered.kind() == Unfiltered.Kind.RANGE_TOMBSTONE_MARKER)
        {
            serialize((RangeTombstoneMarker) unfiltered, header, out, previousUnfilteredSize, version);
        }
        else
        {
            serialize((Row) unfiltered, header, out, previousUnfilteredSize, version);
        }
    }

    public void serializeStaticRow(Row row, SerializationHeader header, DataOutputPlus out, int version)
    throws IOException
    {
        assert row.isStatic();
        serialize(row, header, out, 0, version);
    }

    private void serialize(Row row, SerializationHeader header, DataOutputPlus out, long previousUnfilteredSize, int version)
    throws IOException
    {
        int flags = 0;
        int extendedFlags = 0;

        boolean isStatic = row.isStatic();
        Columns headerColumns = header.columns(isStatic);
        LivenessInfo pkLiveness = row.primaryKeyLivenessInfo();
        Row.Deletion deletion = row.deletion();
        boolean hasComplexDeletion = row.hasComplexDeletion();
        boolean hasAllColumns = (row.size() == headerColumns.size());
        boolean hasExtendedFlags = hasExtendedFlags(row);

        if (isStatic)
            extendedFlags |= IS_STATIC;

        if (!pkLiveness.isEmpty())
            flags |= HAS_TIMESTAMP;
        if (pkLiveness.isExpiring())
            flags |= HAS_TTL;
        if (!deletion.isLive())
        {
            flags |= HAS_DELETION;
            if (deletion.isShadowable())
                extendedFlags |= HAS_SHADOWABLE_DELETION;
        }
        if (hasComplexDeletion)
            flags |= HAS_COMPLEX_DELETION;
        if (hasAllColumns)
            flags |= HAS_ALL_COLUMNS;

        if (hasExtendedFlags)
            flags |= EXTENSION_FLAG;

        out.writeByte((byte)flags);
        if (hasExtendedFlags)
            out.writeByte((byte)extendedFlags);

        if (!isStatic)
            Clustering.serializer.serialize(row.clustering(), out, version, header.clusteringTypes());

        if (header.isForSSTable())
        {
            out.writeUnsignedVInt(serializedRowBodySize(row, header, previousUnfilteredSize, version));
            // We write the size of the previous unfiltered to make reverse queries more efficient (and simpler).
            // This is currently not used however and using it is tbd.
            out.writeUnsignedVInt(previousUnfilteredSize);
        }

        if ((flags & HAS_TIMESTAMP) != 0)
            header.writeTimestamp(pkLiveness.timestamp(), out);
        if ((flags & HAS_TTL) != 0)
        {
            header.writeTTL(pkLiveness.ttl(), out);
            header.writeLocalDeletionTime(pkLiveness.localExpirationTime(), out);
        }
        if ((flags & HAS_DELETION) != 0)
            header.writeDeletionTime(deletion.time(), out);

        if (!hasAllColumns)
            Columns.serializer.serializeSubset(Collections2.transform(row, ColumnData::column), headerColumns, out);

        for (ColumnData data : row)
        {
            if (data.column.isSimple())
                Cell.serializer.serialize((Cell) data, out, pkLiveness, header);
            else
                writeComplexColumn((ComplexColumnData) data, hasComplexDeletion, pkLiveness, header, out);
        }
    }

    private void writeComplexColumn(ComplexColumnData data, boolean hasComplexDeletion, LivenessInfo rowLiveness, SerializationHeader header, DataOutputPlus out)
    throws IOException
    {
        if (hasComplexDeletion)
            header.writeDeletionTime(data.complexDeletion(), out);

        out.writeUnsignedVInt(data.cellsCount());
        for (Cell cell : data)
            Cell.serializer.serialize(cell, out, rowLiveness, header);
    }

    private void serialize(RangeTombstoneMarker marker, SerializationHeader header, DataOutputPlus out, long previousUnfilteredSize, int version)
    throws IOException
    {
        out.writeByte((byte)IS_MARKER);
        ClusteringBoundOrBoundary.serializer.serialize(marker.clustering(), out, version, header.clusteringTypes());

        if (header.isForSSTable())
        {
            out.writeUnsignedVInt(serializedMarkerBodySize(marker, header, previousUnfilteredSize, version));
            out.writeUnsignedVInt(previousUnfilteredSize);
        }

        if (marker.isBoundary())
        {
            RangeTombstoneBoundaryMarker bm = (RangeTombstoneBoundaryMarker)marker;
            header.writeDeletionTime(bm.endDeletionTime(), out);
            header.writeDeletionTime(bm.startDeletionTime(), out);
        }
        else
        {
            header.writeDeletionTime(((RangeTombstoneBoundMarker)marker).deletionTime(), out);
        }
    }

    public long serializedSize(Unfiltered unfiltered, SerializationHeader header, int version)
    {
        assert !header.isForSSTable();
        return serializedSize(unfiltered, header, 0, version);
    }

    public long serializedSize(Unfiltered unfiltered, SerializationHeader header, long previousUnfilteredSize,int version)
    {
        return unfiltered.kind() == Unfiltered.Kind.RANGE_TOMBSTONE_MARKER
             ? serializedSize((RangeTombstoneMarker) unfiltered, header, previousUnfilteredSize, version)
             : serializedSize((Row) unfiltered, header, previousUnfilteredSize, version);
    }

    private long serializedSize(Row row, SerializationHeader header, long previousUnfilteredSize, int version)
    {
        long size = 1; // flags

        if (hasExtendedFlags(row))
            size += 1; // extended flags

        if (!row.isStatic())
            size += Clustering.serializer.serializedSize(row.clustering(), version, header.clusteringTypes());

        return size + serializedRowBodySize(row, header, previousUnfilteredSize, version);
    }

    private long serializedRowBodySize(Row row, SerializationHeader header, long previousUnfilteredSize, int version)
    {
        long size = 0;

        if (header.isForSSTable())
            size += TypeSizes.sizeofUnsignedVInt(previousUnfilteredSize);

        boolean isStatic = row.isStatic();
        Columns headerColumns = header.columns(isStatic);
        LivenessInfo pkLiveness = row.primaryKeyLivenessInfo();
        Row.Deletion deletion = row.deletion();
        boolean hasComplexDeletion = row.hasComplexDeletion();
        boolean hasAllColumns = (row.size() == headerColumns.size());

        if (!pkLiveness.isEmpty())
            size += header.timestampSerializedSize(pkLiveness.timestamp());
        if (pkLiveness.isExpiring())
        {
            size += header.ttlSerializedSize(pkLiveness.ttl());
            size += header.localDeletionTimeSerializedSize(pkLiveness.localExpirationTime());
        }
        if (!deletion.isLive())
            size += header.deletionTimeSerializedSize(deletion.time());

        if (!hasAllColumns)
            size += Columns.serializer.serializedSubsetSize(Collections2.transform(row, ColumnData::column), header.columns(isStatic));

        for (ColumnData data : row)
        {
            if (data.column.isSimple())
                size += Cell.serializer.serializedSize((Cell) data, pkLiveness, header);
            else
                size += sizeOfComplexColumn((ComplexColumnData) data, hasComplexDeletion, pkLiveness, header);
        }

        return size;
    }

    private long sizeOfComplexColumn(ComplexColumnData data, boolean hasComplexDeletion, LivenessInfo rowLiveness, SerializationHeader header)
    {
        long size = 0;

        if (hasComplexDeletion)
            size += header.deletionTimeSerializedSize(data.complexDeletion());

        size += TypeSizes.sizeofUnsignedVInt(data.cellsCount());
        for (Cell cell : data)
            size += Cell.serializer.serializedSize(cell, rowLiveness, header);

        return size;
    }

    private long serializedSize(RangeTombstoneMarker marker, SerializationHeader header, long previousUnfilteredSize, int version)
    {
        assert !header.isForSSTable();
        return 1 // flags
             + ClusteringBoundOrBoundary.serializer.serializedSize(marker.clustering(), version, header.clusteringTypes())
             + serializedMarkerBodySize(marker, header, previousUnfilteredSize, version);
    }

    private long serializedMarkerBodySize(RangeTombstoneMarker marker, SerializationHeader header, long previousUnfilteredSize, int version)
    {
        long size = 0;
        if (header.isForSSTable())
            size += TypeSizes.sizeofUnsignedVInt(previousUnfilteredSize);

        if (marker.isBoundary())
        {
            RangeTombstoneBoundaryMarker bm = (RangeTombstoneBoundaryMarker)marker;
            size += header.deletionTimeSerializedSize(bm.endDeletionTime());
            size += header.deletionTimeSerializedSize(bm.startDeletionTime());
        }
        else
        {
           size += header.deletionTimeSerializedSize(((RangeTombstoneBoundMarker)marker).deletionTime());
        }
        return size;
    }

    public void writeEndOfPartition(DataOutputPlus out) throws IOException
    {
        out.writeByte((byte)1);
    }

    public long serializedSizeEndOfPartition()
    {
        return 1;
    }

    public Unfiltered deserialize(DataInputPlus in, SerializationHeader header, SerializationHelper helper, Row.Builder builder)
    throws IOException
    {
        // It wouldn't be wrong per-se to use an unsorted builder, but it would be inefficient so make sure we don't do it by mistake
        assert builder.isSorted();

        int flags = in.readUnsignedByte();
        if (isEndOfPartition(flags))
            return null;

        int extendedFlags = readExtendedFlags(in, flags);

        if (kind(flags) == Unfiltered.Kind.RANGE_TOMBSTONE_MARKER)
        {
            ClusteringBoundOrBoundary bound = ClusteringBoundOrBoundary.serializer.deserialize(in, helper.version, header.clusteringTypes());
            return deserializeMarkerBody(in, header, bound);
        }
        else
        {
            // deserializeStaticRow should be used for that.
            if (isStatic(extendedFlags))
                throw new IOException("Corrupt flags value for unfiltered partition (isStatic flag set): " + flags);

            builder.newRow(Clustering.serializer.deserialize(in, helper.version, header.clusteringTypes()));
            Row row = deserializeRowBody(in, header, helper, flags, extendedFlags, builder);
            // we do not write empty rows because Rows.collectStats(), called by BTW.applyToRow(), asserts that rows are not empty
            // if we don't throw here, then later the very same assertion in Rows.collectStats() will fail compactions
            // see BlackListingCompactionsTest and CASSANDRA-9530 for details
            if (row.isEmpty())
                throw new IOException("Corrupt empty row found in unfiltered partition");
            return row;
        }
    }

    public Row deserializeStaticRow(DataInputPlus in, SerializationHeader header, SerializationHelper helper)
    throws IOException
    {
        int flags = in.readUnsignedByte();
        assert !isEndOfPartition(flags) && kind(flags) == Unfiltered.Kind.ROW && isExtended(flags) : flags;
        int extendedFlags = in.readUnsignedByte();
        Row.Builder builder = BTreeRow.sortedBuilder();
        builder.newRow(Clustering.STATIC_CLUSTERING);
        return deserializeRowBody(in, header, helper, flags, extendedFlags, builder);
    }

    public RangeTombstoneMarker deserializeMarkerBody(DataInputPlus in, SerializationHeader header, ClusteringBoundOrBoundary bound)
    throws IOException
    {
        if (header.isForSSTable())
        {
            in.readUnsignedVInt(); // marker size
            in.readUnsignedVInt(); // previous unfiltered size
        }

        if (bound.isBoundary())
            return new RangeTombstoneBoundaryMarker((ClusteringBoundary) bound, header.readDeletionTime(in), header.readDeletionTime(in));
        else
            return new RangeTombstoneBoundMarker((ClusteringBound) bound, header.readDeletionTime(in));
    }

    public Row deserializeRowBody(DataInputPlus in,
                                  SerializationHeader header,
                                  SerializationHelper helper,
                                  int flags,
                                  int extendedFlags,
                                  Row.Builder builder)
    throws IOException
    {
        try
        {
            boolean isStatic = isStatic(extendedFlags);
            boolean hasTimestamp = (flags & HAS_TIMESTAMP) != 0;
            boolean hasTTL = (flags & HAS_TTL) != 0;
            boolean hasDeletion = (flags & HAS_DELETION) != 0;
            boolean deletionIsShadowable = (extendedFlags & HAS_SHADOWABLE_DELETION) != 0;
            boolean hasComplexDeletion = (flags & HAS_COMPLEX_DELETION) != 0;
            boolean hasAllColumns = (flags & HAS_ALL_COLUMNS) != 0;
            Columns headerColumns = header.columns(isStatic);

            if (header.isForSSTable())
            {
                in.readUnsignedVInt(); // Skip row size
                in.readUnsignedVInt(); // previous unfiltered size
            }

            LivenessInfo rowLiveness = LivenessInfo.EMPTY;
            if (hasTimestamp)
            {
                long timestamp = header.readTimestamp(in);
                int ttl = hasTTL ? header.readTTL(in) : LivenessInfo.NO_TTL;
                int localDeletionTime = hasTTL ? header.readLocalDeletionTime(in) : LivenessInfo.NO_EXPIRATION_TIME;
                rowLiveness = LivenessInfo.withExpirationTime(timestamp, ttl, localDeletionTime);
            }

            builder.addPrimaryKeyLivenessInfo(rowLiveness);
            builder.addRowDeletion(hasDeletion ? new Row.Deletion(header.readDeletionTime(in), deletionIsShadowable) : Row.Deletion.LIVE);

            Columns columns = hasAllColumns ? headerColumns : Columns.serializer.deserializeSubset(headerColumns, in);
            for (ColumnDefinition column : columns)
            {
                if (column.isSimple())
                    readSimpleColumn(column, in, header, helper, builder, rowLiveness);
                else
                    readComplexColumn(column, in, header, helper, hasComplexDeletion, builder, rowLiveness);
            }

            return builder.build();
        }
        catch (RuntimeException | AssertionError e)
        {
            // Corrupted data could be such that it triggers an assertion in the row Builder, or break one of its assumption.
            // Of course, a bug in said builder could also trigger this, but it's impossible a priori to always make the distinction
            // between a real bug and data corrupted in just the bad way. Besides, re-throwing as an IOException doesn't hide the
            // exception, it just make we catch it properly and mark the sstable as corrupted.
            throw new IOException("Error building row with data deserialized from " + in, e);
        }
    }

    private void readSimpleColumn(ColumnDefinition column, DataInputPlus in, SerializationHeader header, SerializationHelper helper, Row.Builder builder, LivenessInfo rowLiveness)
    throws IOException
    {
        if (helper.includes(column))
        {
            Cell cell = Cell.serializer.deserialize(in, rowLiveness, column, header, helper);
            if (helper.includes(cell, rowLiveness) && !helper.isDropped(cell, false))
                builder.addCell(cell);
        }
        else
        {
            Cell.serializer.skip(in, column, header);
        }
    }

    private void readComplexColumn(ColumnDefinition column, DataInputPlus in, SerializationHeader header, SerializationHelper helper, boolean hasComplexDeletion, Row.Builder builder, LivenessInfo rowLiveness)
    throws IOException
    {
        if (helper.includes(column))
        {
            helper.startOfComplexColumn(column);
            if (hasComplexDeletion)
            {
                DeletionTime complexDeletion = header.readDeletionTime(in);
                if (!helper.isDroppedComplexDeletion(complexDeletion))
                    builder.addComplexDeletion(column, complexDeletion);
            }

            int count = (int) in.readUnsignedVInt();
            while (--count >= 0)
            {
                Cell cell = Cell.serializer.deserialize(in, rowLiveness, column, header, helper);
                if (helper.includes(cell, rowLiveness) && !helper.isDropped(cell, true))
                    builder.addCell(cell);
            }

            helper.endOfComplexColumn();
        }
        else
        {
            skipComplexColumn(in, column, header, hasComplexDeletion);
        }
    }

    public void skipRowBody(DataInputPlus in) throws IOException
    {
        int rowSize = (int)in.readUnsignedVInt();
        in.skipBytesFully(rowSize);
    }

    public void skipStaticRow(DataInputPlus in, SerializationHeader header, SerializationHelper helper) throws IOException
    {
        int flags = in.readUnsignedByte();
        assert !isEndOfPartition(flags) && kind(flags) == Unfiltered.Kind.ROW && isExtended(flags) : "Flags is " + flags;
        int extendedFlags = in.readUnsignedByte();
        assert isStatic(extendedFlags);
        skipRowBody(in);
    }

    public void skipMarkerBody(DataInputPlus in) throws IOException
    {
        int markerSize = (int)in.readUnsignedVInt();
        in.skipBytesFully(markerSize);
    }

    private void skipComplexColumn(DataInputPlus in, ColumnDefinition column, SerializationHeader header, boolean hasComplexDeletion)
    throws IOException
    {
        if (hasComplexDeletion)
            header.skipDeletionTime(in);

        int count = (int) in.readUnsignedVInt();
        while (--count >= 0)
            Cell.serializer.skip(in, column, header);
    }

    public static boolean isEndOfPartition(int flags)
    {
        return (flags & END_OF_PARTITION) != 0;
    }

    public static Unfiltered.Kind kind(int flags)
    {
        return (flags & IS_MARKER) != 0 ? Unfiltered.Kind.RANGE_TOMBSTONE_MARKER : Unfiltered.Kind.ROW;
    }

    public static boolean isStatic(int extendedFlags)
    {
        return (extendedFlags & IS_STATIC) != 0;
    }

    private static boolean isExtended(int flags)
    {
        return (flags & EXTENSION_FLAG) != 0;
    }

    public static int readExtendedFlags(DataInputPlus in, int flags) throws IOException
    {
        return isExtended(flags) ? in.readUnsignedByte() : 0;
    }

    public static boolean hasExtendedFlags(Row row)
    {
        return row.isStatic() || row.deletion().isShadowable();
    }
}
