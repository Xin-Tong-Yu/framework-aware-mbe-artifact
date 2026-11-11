#ifndef GRAPH_HPP
#define GRAPH_HPP

#include <vector>
#include <memory>
#include <cstdint>
#include <algorithm>
#include <queue>
#include <iostream>
#include <unordered_set>
#include <sys/resource.h>
#include <random>
#include "io.hpp"
#include "heap.hpp"
#include "hash.hpp"


struct Edge {
    int32_t u{}, v{};

    Edge() = default;

    Edge (int eu, int ev) {
        u = eu, v = ev;
    }

    bool operator==(const Edge& e) const {
        return u == e.u && v == e.v;
    }

    bool operator< (const Edge& e) const {
        return u < e.u || (u == e.u && v < e.v);
    }

    uint64_t operator()(const Edge& e) const {
        size_t hash = (((uint64_t) e.u) << 32) | (uint64_t) e.v;
        return hash;
    };
};

namespace std {
    template<> struct hash<Edge>
    {
        std::size_t operator()(const Edge& e) const noexcept
        {
            return e(e);
        }
    };
}


void clean_edges(const char *r_file_name, const char *w_file_name) {
    std::unordered_set<Edge> E;
    int s, t;
    FILE *f_r = fopen(r_file_name, "r");
    FILE *f_w = fopen(w_file_name, "w");

    while (fscanf(f_r, "%u %u%*[^\n]%*c", &s, &t) == 2) {

        if (E.find(Edge(s, t)) != E.end()) {
            printf("(%u, %u) duplicates.\n", s, t);
            continue;
        }

        E.insert(Edge(s, t));
        fprintf(f_w, "%u %u\n", s, t);
    }

    fclose(f_r);
    fclose(f_w);
}

void gen_vertex(const char *r_file_name, const char* w_file_name, double p) {

    int s, t, n1, n2, m;
    FILE *f_r = fopen(r_file_name, "r");
    FILE *f_w = fopen(w_file_name, "w");

    assert(fscanf(f_r, "%d %d %d", &n1, &n2, &m) == 3);

    std::vector<bool> h1(n1), h2(n2);

    std::random_device rd;
    std::mt19937 gen(rd());
    std::bernoulli_distribution d(p);

    for (int i = 0; i <= n1; i++) h1[i] = d(gen);
    for (int i = 0; i <= n2; i++) h2[i] = d(gen);

    fprintf(f_w, "%d %d %d\n", n1, n2, m);

    while (fscanf(f_r, "%u %u%*[^\n]%*c", &s, &t) == 2) {
        if (h1[s] && h2[t]) fprintf(f_w, "%u %u\n", s, t);
    }

    fclose(f_r);
    fclose(f_w);
}

void gen_edge(const char *r_file_name, const char* w_file_name, double p) {
    int s, t, n1, n2, m;

    FILE *f_r = fopen(r_file_name, "r");
    FILE *f_w = fopen(w_file_name, "w");

    std::random_device rd;
    std::mt19937 gen(rd());
    std::bernoulli_distribution d(p);

    assert(fscanf(f_r, "%d %d %d", &n1, &n2, &m) == 3);

    fprintf(f_w, "%d %d %d\n", n1, n2, m);

    while (fscanf(f_r, "%u %u%*[^\n]%*c", &s, &t) == 2) {
        if (d(gen)) fprintf(f_w, "%u %u\n", s, t);
    }

    fclose(f_r);
    fclose(f_w);
}

void gen_plex(const char* w_file_name, int n) {
    FILE *f_w = fopen(w_file_name, "w");

    fprintf(f_w, "%d %d %d\n", n, n, n * (n - 1));

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i == j) continue;

            fprintf(f_w, "%d %d\n", i, j);
        }
    }

    fclose(f_w);
}

class BiGraph_t {

public:
    int32_t n1, n2, m, maxDu, maxDv;
    int32_t core[2];
    int32_t n[2];

    std::vector <Edge> edges;

    std::vector <int32_t> pU, e1, pV, e2;
    std::vector <int32_t> p[2];
    std::vector <int32_t> e[2];
    std::vector <int32_t> cores[2];

    std::vector <CuckooHash> cuhash[2];
#ifndef IPS_BITSET_THRESHOLD
#define IPS_BITSET_THRESHOLD 32
#endif
#ifndef IPS_DISABLE_ST
    std::vector<int64_t> bitOffset[2];
    std::vector<uint64_t> bitData[2];
    int32_t bitWords[2] = {0, 0};
#endif

#ifdef IPS_PREFIX_SHARE
    // Root-prefix adjacency memo: only edges to the current root's neighbor set
    // are stored. This is one shared prefix per IPS recursion subtree, not a
    // 2024-style Candidate/Result Prefix Tree.
    struct PrefixEntry { uint32_t epoch = 0, probes = 0; int32_t mask_id = -1; };
    struct PrefixMask { std::unique_ptr<uint64_t[]> words; };
    std::vector<PrefixEntry> prefixEntries[2];
    std::vector<int32_t> prefixPositions, prefixOldNeighbors;
    std::vector<PrefixMask> prefixMasks;
    uint32_t prefixEpoch=1;
    int32_t prefixSide=-1, prefixWords=0;
    bool prefixActive=false;
    size_t prefixMemoryBytes=0;
    uint64_t prefixRowsBuilt=0, prefixCachedProbeCalls=0, prefixRowProbeCalls=0;

    void beginRootPrefix(int32_t t, int32_t root) {
        for(int32_t v: prefixOldNeighbors)prefixPositions[v]=-1;
        prefixOldNeighbors.clear();
        prefixMasks.clear();
        prefixMemoryBytes=0;
        prefixSide=t;
        if(++prefixEpoch==0) {
            for(auto &e:prefixEntries[0])e.epoch=0;
            for(auto &e:prefixEntries[1])e.epoch=0;
            prefixEpoch=1;
        }
        const int32_t len = deg(root,t);
        prefixActive=(len>=16 && len<=4096);
        if(!prefixActive) { prefixWords=0; return; }
        const int32_t z=t^1;
        if(prefixPositions.size() != (size_t)n[z])prefixPositions.assign(n[z],-1);
        prefixWords=(len+63)>>6;
        prefixOldNeighbors.reserve(len);
        for(int32_t i=p[t][root];i<p[t][root+1];++i){
            int32_t v=e[t][i];
            prefixPositions[v]=(int32_t)prefixOldNeighbors.size();
            prefixOldNeighbors.push_back(v);
        }
        if(prefixEntries[t].size() != (size_t)n[t])prefixEntries[t].resize(n[t]);
    }

    const uint64_t *getPrefixRow(int32_t u, int32_t t) {
        if(!prefixActive || t!=prefixSide || deg(u,t)<5 ||
           deg(u,t)>=IPS_BITSET_THRESHOLD) return nullptr;
        ++prefixRowProbeCalls;
        PrefixEntry &entry=prefixEntries[t][u];
        if(entry.epoch !=prefixEpoch) {
            entry.epoch=prefixEpoch;
            entry.probes=0;
            entry.mask_id=-1;
        }
        if(entry.mask_id>=0){
            ++prefixCachedProbeCalls;
            return prefixMasks[entry.mask_id].words.get();
        }
        if(++entry.probes < 16 || prefixMemoryBytes+(size_t)prefixWords*8>8*1024*1024)
            return nullptr;
        PrefixMask m;
        m.words.reset(new uint64_t[prefixWords]());
        for(int32_t i=p[t][u];i<p[t][u+1];++i) {
            int32_t v=e[t][i];
            int32_t at=prefixPositions[v];
            if(at>=0)m.words[at>>6]|=1ULL<<(at&63);
        }
        entry.mask_id=(int32_t)prefixMasks.size();
        prefixMasks.emplace_back(std::move(m));
        prefixMemoryBytes+=(size_t)prefixWords*8;
        ++prefixRowsBuilt;
        ++prefixCachedProbeCalls;
        return prefixMasks.back().words.get();
    }
#endif

    std::vector <int32_t> old_lables[2];

    int32_t lrs[2];
    int32_t k = 0;

    BiGraph_t() = default;

    BiGraph_t(const std::string &filePath, const std::string &order, int32_t ls, int32_t rs) {
        lrs[0] = ls;
        lrs[1] = rs;

        read(filePath, order);
        fprintf(stderr, "[GRAPH_STAGE] read: nL=%d nR=%d m=%d maxDu=%d maxDv=%d\n", n[0],n[1],m,maxDu,maxDv);
        fflush(stderr);

        cuhash[0].resize(n[0]);
        cuhash[1].resize(n[1]);
        for (int32_t t = 0; t <= 1; t++) {
            for (int32_t i = 0; i < n[t]; i++) {
                int32_t d = p[t][i + 1] - p[t][i];
#if defined(IPS_ST_V15_HASHLESS) && !defined(IPS_DISABLE_ST)
                // High-degree vertices are always queried through their full-range
                // bitmap. Building a second CuckooHash for them wastes memory.
                if (d >= IPS_BITSET_THRESHOLD) continue;
#endif
                cuhash[t][i].reserve(d + 1);
                for (int32_t j = p[t][i]; j < p[t][i + 1]; ++j)
                    cuhash[t][i].insert(e[t][j]);
            }
        }
        fprintf(stderr, "[GRAPH_STAGE] cuckoo hashes ready\n");
        fflush(stderr);
#ifndef IPS_DISABLE_ST
        // This memory guard changes only physical adjacency representation.
        // Missing bitmap rows fall back to the already-built exact CuckooHash.
        // It is therefore safe only with the ordinary, non-HASHLESS build.
#ifndef IPS_MAX_BITMAP_MIB
#define IPS_MAX_BITMAP_MIB 256
#endif
        uint64_t bitmapRemaining = (uint64_t)IPS_MAX_BITMAP_MIB * 1024ULL * 1024ULL;
        for (int32_t t = 0; t <= 1; ++t) {
            const int32_t z = t ^ 1;
            bitWords[t] = (n[z] + 63) >> 6;
            bitOffset[t].assign(n[t], -1);
            int64_t rows = 0;
            for (int32_t u = 0; u < n[t]; ++u)
                if (p[t][u+1] - p[t][u] >= IPS_BITSET_THRESHOLD) ++rows;
            const uint64_t estimate = (uint64_t)rows * (uint64_t)bitWords[t] * 8ULL;
            fprintf(stderr, "[BITMAP_GUARD] side=%d rows=%lld width=%d estimate_MiB=%.1f available_MiB=%.1f\n",
                    (int)t,(long long)rows,(int)bitWords[t],estimate/1048576.0,bitmapRemaining/1048576.0);
            fflush(stderr);
#ifndef IPS_ST_V15_HASHLESS
            if (estimate > bitmapRemaining) {
                fprintf(stderr,"[BITMAP_GUARD] side=%d skipped; all queries use exact hash fallback\n",(int)t);
                continue;
            }
#else
            // HASHLESS deliberately omits the high-degree hash, and cannot fall back.
            // The pure experiment modes never define IPS_ST_V15_HASHLESS.
#endif
            int64_t builtRows=0;
            for (int32_t u=0;u<n[t];++u)
                if (p[t][u+1] - p[t][u] >= IPS_BITSET_THRESHOLD)
                    bitOffset[t][u] = (builtRows++) * bitWords[t];
            bitData[t].assign((size_t)builtRows * (size_t)bitWords[t], 0ULL);
            for (int32_t u = 0; u < n[t]; ++u) {
                int64_t off = bitOffset[t][u];
                if (off < 0) continue;
                for (int32_t j = p[t][u]; j < p[t][u + 1]; ++j) {
                    int32_t v = e[t][j];
                    bitData[t][off + (v >> 6)] |= 1ULL << (v & 63);
                }
            }
            if (estimate <= bitmapRemaining) bitmapRemaining-=estimate;
            fprintf(stderr,"[BITMAP_GUARD] side=%d allocated_MiB=%.1f\n",(int)t, estimate/1048576.0);
        }
        fprintf(stderr,"[GRAPH_STAGE] bitmaps ready\n");
        fflush(stderr);
#endif
    }

    void read(const std::string &filePath, const std::string &order) {

        FILE *f = fopen(filePath.c_str(), "r");
        if (f == nullptr || fscanf(f, "%d %d %d", &n1, &n2, &m) != 3) {
            fprintf(stderr, "Cannot read graph header from %s\n", filePath.c_str());
            exit(1);
        }

//        n1 = in.getUInt();
//        n2 = in.getUInt();
//        m = in.getUInt();

        edges.resize(m);
        e1.resize(m);
        e2.resize(m);
        pU.resize(n1 + 5);
        pV.resize(n2 + 5);

       int i = 0, s, t;

        while (fscanf(f, "%u %u%*[^\n]%*c", &s, &t) == 2) {
            if (i >= m) {
                printf("Enlarge number of e to %d.\n", i + 1);
                exit(0);
            }
            if (s >= n1) {
                printf("Enlarge number of v1 to %d.\n", s + 1);
                exit(0);
            }
            if (t >= n2) {
                printf("Enlarge number of v2 to %d.\n", t + 1);
                exit(0);
            }

            edges[i].u = s;
            edges[i++].v = t;
        }

        m = i;

        edges.resize(i);
        e1.resize(i);
        e2.resize(i);

        fclose(f);

        cores[0].resize(n1);
        cores[1].resize(n2);
        old_lables[0].resize(n1);
        old_lables[1].resize(n2);

        if (order == "core") changeToCoreOrderVersion2();
        else if (order == "two") changeToTwoHopCoreOrder();
        else if (order == "deg") changeToDegreeOrder();
        else if (order == "raw") rawOrder();
        else {
            printf("error order\n");
            exit(1);
        }

        n[0] = n1;
        n[1] = n2;
        p[0] = std::move(pU);
        p[1] = std::move(pV);
        e[0] = std::move(e1);
        e[1] = std::move(e2);
    }

    void changeToTwoHopCoreOrder() {
        std::vector <int32_t> d1, d2;

        d1.resize(n1);
        d2.resize(n2);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        maxDu = 0;
        for (int32_t i = 0; i < n1; i++) {
            maxDu = std::max(maxDu, d1[i]);
        }
        maxDv = 0;
        for (int32_t i = 0; i < n2; i++) {
            maxDv = std::max(maxDv, d2[i]);
        }

        pU[0] = 0;
        for (int32_t u = 0; u < n1; u++) {
            pU[u + 1] = d1[u] + pU[u];
        }
        for (int32_t i = 0; i < m; i++) {
            e1[pU[edges[i].u]++] = edges[i].v;
        }
        pU[0] = 0;
        for (int32_t u = 0; u < n1; u++) {
            pU[u + 1] = d1[u] + pU[u];
        }

        pV[0] = 0;
        for (int32_t v = 0; v < n2; v++) {
            pV[v + 1] = d2[v] + pV[v];
        }
        for (int32_t i = 0; i < m; i++) {
            e2[pV[edges[i].v]++] = edges[i].u;
        }
        pV[0] = 0;
        for (int32_t v = 0; v < n2; v++) {
            pV[v + 1] = d2[v] + pV[v];
        }

        int32_t N = n1 + n2;
        std::vector <int32_t> dequeue;
        std::vector <int32_t> cdeg;
        dequeue.resize(N);
        cdeg.resize(N, 0);
        int32_t tsize = 0;

        n[0] = n1;
        n[1] = n2;
        for (int32_t tt = 0; tt <= 1; tt++) {
            for (int32_t i = 0; i < n[tt]; i++) {
                int32_t d = 0;
                if (tt == 0) {
                    d = d1[i];
                    cdeg[i] = d;
                    if (d + k < lrs[1])
                        dequeue[tsize++] = i;
                } else {
                    d = d2[i];
                    cdeg[i + n1] = d;
                    if (d + k < lrs[0])
                        dequeue[tsize++] = i + n1;
                }
            }
        }


        int32_t rsize = 0;
        while (tsize > rsize) {
            int32_t s = rsize;
            rsize = tsize;
            for (int32_t i = s; i < rsize; ++i) {
                int v = dequeue[i];
                if (v >= n1) {
                    v -= n1;
                    for (int32_t j = pV[v]; j < pV[v + 1]; ++j) {
                        int32_t u = e2[j];
                        if (cdeg[u] + k >= lrs[1]) {
                            cdeg[u]--;
                            if (cdeg[u] + k < lrs[1])
                                dequeue[tsize++] = u;
                        }
                    }
                } else {
                    for (int32_t j = pU[v]; j < pU[v + 1]; ++j) {
                        int32_t u = e1[j];
                        u += n1;
                        if (cdeg[u] + k >= lrs[0]) {
                            cdeg[u]--;
                            if (cdeg[u] + k < lrs[0])
                                dequeue[tsize++] = u;
                        }
                    }
                }
            }
        }

        int32_t maxTwoHopDegreeU = 0, maxTwoHopDegreeV = 0;
        d1.clear();
        std::vector <int32_t> stk;
        int32_t n = std::max(n1, n2);
        std::vector <int32_t> ids(n);
        std::vector <int32_t> keys(n);
        std::vector <int32_t> labelsL(n1);
        std::vector <int32_t> labelsR(n2);
        int32_t l = 0;

        for (int32_t u = 0; u < n1; u++) ids[u] = u;
        for (int32_t u = 0; u < n1; u++) {
            if (cdeg[u] + k < lrs[1]) {
                keys[u] = 0;
                continue;
            }
            stk.clear();
            int32_t tmp = 0;

            for (int32_t i = pU[u]; i < pU[u + 1]; i++) {
                int32_t v = e1[i];
                if (cdeg[v + n1] + k < lrs[0]) continue;
                tmp++;
                for (int32_t j = pV[v]; j < pV[v + 1]; j++) {
                    int32_t w = e2[j];
                    if (d1[w] == 0 && cdeg[w] + k >= lrs[1]) {
                        d1[w] = 1;
                        stk.push_back(w);
                    }
                }
            }
            tmp += stk.size();

            maxTwoHopDegreeU = std::max(maxTwoHopDegreeU, tmp);
            keys[u] = tmp;

            for (auto w: stk) d1[w] = 0;
        }

        Heap_t heap(n1, maxTwoHopDegreeU + 1);
        heap.init(n1, maxTwoHopDegreeU + 1, ids.data(), keys.data());
        core[0] = 0;
        core[1] = 0;

        for (int32_t i = 0; i < n1; i++) {
            int32_t u, degU;

            if (!heap.pop_min(u, degU)) printf("errorLheap\n");
            old_lables[0][l] = u;
            labelsL[u] = l++;
            core[0] = std::max(core[0], degU);
            cores[0][l - 1] = core[0];
            if (core[0] == 0) continue;
            stk.clear();
            for (int32_t i = pU[u]; i < pU[u + 1]; i++) {
                int32_t v = e1[i];
                if (cdeg[v + n1] + k < lrs[0]) continue;
                for (int32_t j = pV[v]; j < pV[v + 1]; j++) {
                    int32_t w = e2[j];
                    if (d1[w] == 0 && cdeg[w] + k >= lrs[1]) {
                        d1[w] = 1;
                        stk.push_back(w);
                        heap.decrement(w, 1);
                    }
                }
            }

            for (auto w: stk) d1[w] = 0;
        }

        d2.clear();
        l = 0;

        for (int32_t u = 0; u < n2; u++) ids[u] = u;
        for (int32_t u = 0; u < n2; u++) {
            if (cdeg[u + n1] + k < lrs[0]) {
                keys[u] = 0;
                continue;
            }
            stk.clear();
            int32_t tmp = 0;

            for (int32_t i = pV[u]; i < pV[u + 1]; i++) {
                int32_t v = e2[i];
                if (cdeg[v] + k < lrs[1]) continue;
                tmp++;
                for (int32_t j = pU[v]; j < pU[v + 1]; j++) {
                    int32_t w = e1[j];
                    if (d2[w] == 0 && cdeg[w + n1] + k >= lrs[0]) {
                        d2[w] = 1;
                        stk.push_back(w);
                    }
                }
            }
            tmp += stk.size();

            maxTwoHopDegreeV = std::max(maxTwoHopDegreeV, tmp);
            keys[u] = tmp;

            for (auto w: stk) d2[w] = 0;
        }

        Heap_t rheap(n2, maxTwoHopDegreeV + 1);
        rheap.init(n2, maxTwoHopDegreeV + 1, ids.data(), keys.data());

        for (int32_t i = 0; i < n2; i++) {
            int32_t u, degU;

            if (!rheap.pop_min(u, degU)) printf("errorLheap\n");
            old_lables[1][l] = u;
            labelsR[u] = l++;
            core[1] = std::max(core[1], degU);
            cores[1][l - 1] = core[1];
            if (core[1] == 0) continue;
            stk.clear();
            for (int32_t i = pV[u]; i < pV[u + 1]; i++) {
                int32_t v = e2[i];
                if (cdeg[v] + k < lrs[1]) continue;
                for (int32_t j = pU[v]; j < pU[v + 1]; j++) {
                    int32_t w = e1[j];
                    if (d2[w] == 0 && cdeg[w + n1] + k >= lrs[0]) {
                        d2[w] = 1;
                        stk.push_back(w);
                        heap.decrement(w, 1);
                    }
                }
            }

            for (auto w: stk) d2[w] = 0;
        }
        for (int32_t i = 0; i < n1; ++i) {
            int v = labelsL[i];
            cores[0][v] = cdeg[i];
        }
        for (int32_t i = 0; i < n2; ++i) {
            int v = labelsR[i];
            cores[1][v] = cdeg[i + n1];
        }

        for (int32_t i = 0; i < m; i++) {
            edges[i].u = labelsL[edges[i].u];
            edges[i].v = labelsR[edges[i].v];
        }

        std::fill(d1.begin(), d1.begin() + n1, 0);
        std::fill(d2.begin(), d2.begin() + n2, 0);
        std::fill(pU.begin(), pU.begin() + n1 + 1, 0);
        std::fill(pV.begin(), pV.begin() + n2 + 1, 0);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        for (int32_t i = 0; i < n1; i++) {
            pU[i + 1] = pU[i] + d1[i];
        }
        for (int32_t i = 0; i < n2; i++) {
            pV[i + 1] = pV[i] + d2[i];
        }

        for (int32_t i = 0; i < m; i++) {
            e1[pU[edges[i].u]++] = edges[i].v;
        }
        for (int32_t i = 0; i < m; i++) {
            e2[pV[edges[i].v]++] = edges[i].u;
        }

        pU[0] = pV[0] = 0;
        for (int32_t i = 0; i < n1; i++) {
            pU[i + 1] = pU[i] + d1[i];
        }
        for (int32_t i = 0; i < n2; i++) {
            pV[i + 1] = pV[i] + d2[i];
        }

        for (int32_t i = 0; i < n1; i++) {
            std::sort(e1.begin() + pU[i], e1.begin() + pU[i + 1]);
        }
        for (int32_t i = 0; i < n2; i++) {
            std::sort(e2.begin() + pV[i], e2.begin() + pV[i + 1]);
        }
    }

//    void coreReduction(int p, int q) {
//        std::queue <int32_t> qL, qR;
//        std::vector <int32_t> d1(n1 + 1), d2(n2 + 1);
//        std::vector <int32_t> labelsL(n1 + 1), labelsR(n2 + 1);
//        std::vector<bool> visL(n1 + 1), visR(n2 + 1);
//
//        for (int32_t i = 0; i < n1; i++) {
//            d1[i] = deg1(i);
//            if (deg1(i) < q) {
//                qL.push(i);
//                visL[i] = true;
//            }
//        }
//        for (int32_t i = 0; i < n2; i++) {
//            d2[i] = deg2(i);
//            if (deg2(i) < p) {
//                qR.push(i);
//                visR[i] = true;
//            }
//        }
//
//        while (!qL.empty() || !qR.empty()) {
//            while (!qL.empty()) {
//                int32_t u = qL.front();
//                qL.pop();
//
//                for (int32_t i = 0; i < d1[u]; i++) {
//                    int32_t v = e1[pU[u] + i];
//                    // if(d2[v] < q) continue;
//
//                    for (int32_t j = pV[v]; j < pV[v] + d2[v]; j++) {
//                        if (e2[j] == u) {
//                            --d2[v];
//                            std::swap(e2[j], e2[pV[v] + d2[v]]);
//
//                            if (d2[v] == p - 1 && !visR[v]) {
//                                qR.push(v);
//                                visR[v] = true;
//                            }
//                            break;
//                        }
//                    }
//                }
//            }
//
//            while (!qR.empty()) {
//                int32_t v = qR.front();
//                qR.pop();
//
//                for (int32_t i = 0; i < d2[v]; i++) {
//                    int32_t u = e2[pV[v] + i];
//                    // if(d1[u] < p) continue;
//
//                    for (int32_t j = pU[u]; j < pU[u] + d1[u]; j++) {
//                        if (e1[j] == v) {
//                            --d1[u];
//                            std::swap(e1[j], e1[pU[u] + d1[u]]);
//
//                            if (d1[u] == q - 1 && !visL[u]) {
//                                qL.push(u);
//                                visL[u] = true;
//                            }
//                            break;
//                        }
//                    }
//                }
//            }
//        }
//
//        int32_t pL = 1, pR = 1;
//        for (int32_t u = 0; u < n1; u++) {
//            if (!visL[u]) labelsL[u] = pL++;
//        }
//        for (int32_t v = 0; v < n2; v++) {
//            if (!visR[v]) labelsR[v] = pR++;
//        }
//
//        int32_t pm = 0;
//        for (int32_t u = 0; u < n1; u++) {
//            if (visL[u]) continue;
//            for (int32_t i = pU[u]; i < pU[u + 1]; i++) {
//                int32_t v = e1[i];
//                if (!visR[v]) {
//                    edges[pm].u = labelsL[u] - 1;
//                    edges[pm].v = labelsR[v] - 1;
//                    ++pm;
//                }
//            }
//        }
//        m = pm;
//
//        n1 = pL - 1;
//        n2 = pR - 1;
//
//        std::fill(pU.begin(), pU.begin() + n1 + 1, 0);
//        std::fill(pV.begin(), pV.begin() + n2 + 1, 0);
//
//        std::fill(d1.begin(), d1.begin() + n1 + 1, 0);
//        std::fill(d2.begin(), d2.begin() + n2 + 1, 0);
//        changeToDegreeOrder();
//
//    }

    void changeToCoreOrderVersion2() {
        std::vector <int32_t> d1, d2;

        d1.resize(n1);
        d2.resize(n2);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        maxDu = 0;
        for (int32_t i = 0; i < n1; i++) {
            maxDu = std::max(maxDu, d1[i]);
        }
        maxDv = 0;
        for (int32_t i = 0; i < n2; i++) {
            maxDv = std::max(maxDv, d2[i]);
        }

        pU[0] = 0;
        for (int32_t u = 0; u < n1; u++) {
            pU[u + 1] = d1[u] + pU[u];
        }
        for (int32_t i = 0; i < m; i++) {
            e1[pU[edges[i].u]++] = edges[i].v;
        }
        pU[0] = 0;
        for (int32_t u = 0; u < n1; u++) {
            pU[u + 1] = d1[u] + pU[u];
        }

        pV[0] = 0;
        for (int32_t v = 0; v < n2; v++) {
            pV[v + 1] = d2[v] + pV[v];
        }
        for (int32_t i = 0; i < m; i++) {
            e2[pV[edges[i].v]++] = edges[i].u;
        }
        pV[0] = 0;
        for (int32_t v = 0; v < n2; v++) {
            pV[v + 1] = d2[v] + pV[v];
        }

        Heap_t l_heap(n1, maxDu + 1), r_heap(n2, maxDv + 1);
        int32_t n = std::max(n1, n2);
        std::vector <int32_t> ids(n);
        std::vector <int32_t> keys(n);
        std::vector <int32_t> labelsL(n1);
        std::vector <int32_t> labelsR(n2);
        int32_t l1 = 0, l2 = 0;

        for (int32_t i = 0; i < n1; i++) {
            ids[i] = i;
            keys[i] = d1[i] + 1;
        }
        l_heap.init(n1, maxDu + 1, ids.data(), keys.data());
        for (int32_t i = 0; i < n2; i++) {
            ids[i] = i;
            keys[i] = d2[i] + 1;
        }
        r_heap.init(n2, maxDv + 1, ids.data(), keys.data());

        core[0] = 0;
        core[1] = 0;
        for (int32_t i = 0; i < n1 + n2; i++) {

//            if (i % 1000 == 0) printf("---- %d %d\n", i, n1 + n2);

            int32_t u, degU = n2 + 11;
            int32_t v, degV = n1 + 11;

            if (!l_heap.empty() && !l_heap.pop_min(u, degU)) printf("error l_heap\n");

            if (!r_heap.empty() && !r_heap.pop_min(v, degV)) printf("error r_heap\n");

            if (degU <= degV) {
                if (degV != n1 + 11) r_heap.insert(v, degV);

                for (int32_t j = pU[u]; j < pU[u + 1]; j++) r_heap.decrement(e1[j]);

                old_lables[0][l1] = u;
                labelsL[u] = l1++;
                core[0] = std::max(core[0], degU);
                cores[0][l1 - 1] = core[0];
            } else {
                if (degU != n2 + 11) l_heap.insert(u, degU);

                for (int32_t j = pV[v]; j < pV[v + 1]; j++) l_heap.decrement(e2[j]);

                old_lables[1][l2] = v;
                labelsR[v] = l2++;
                core[1] = std::max(core[1], degV);
                cores[1][l2 - 1] = core[1];
            }
        }

        for (int32_t i = 0; i < m; i++) {
            edges[i].u = labelsL[edges[i].u];
            edges[i].v = labelsR[edges[i].v];
        }

        std::fill(d1.begin(), d1.begin() + n1, 0);
        std::fill(d2.begin(), d2.begin() + n2, 0);
        std::fill(pU.begin(), pU.begin() + n1 + 1, 0);
        std::fill(pV.begin(), pV.begin() + n2 + 1, 0);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        for (int32_t i = 0; i < n1; i++) {
            pU[i + 1] = pU[i] + d1[i];
        }
        for (int32_t i = 0; i < n2; i++) {
            pV[i + 1] = pV[i] + d2[i];
        }

        for (int32_t i = 0; i < m; i++) {
            e1[pU[edges[i].u]++] = edges[i].v;
        }
        for (int32_t i = 0; i < m; i++) {
            e2[pV[edges[i].v]++] = edges[i].u;
        }

        pU[0] = pV[0] = 0;
        for (int32_t i = 0; i < n1; i++) {
            pU[i + 1] = pU[i] + d1[i];
        }
        for (int32_t i = 0; i < n2; i++) {
            pV[i + 1] = pV[i] + d2[i];
        }

        for (int32_t i = 0; i < n1; i++) {
            std::sort(e1.begin() + pU[i], e1.begin() + pU[i + 1]);
        }
        for (int32_t i = 0; i < n2; i++) {
            std::sort(e2.begin() + pV[i], e2.begin() + pV[i + 1]);
        }

    }

//    void changeToCoreOrder() {
//        std::vector <int32_t> d1, d2;
//
//        d1.resize(n1);
//        d2.resize(n2);
//
//        for (int32_t i = 0; i < m; i++) {
//            ++d1[edges[i].u];
//            ++d2[edges[i].v];
//        }
//
//        maxDu = 0;
//        for (int32_t i = 0; i < n1; i++) {
//            maxDu = std::max(maxDu, d1[i]);
//        }
//        maxDv = 0;
//        for (int32_t i = 0; i < n2; i++) {
//            maxDv = std::max(maxDv, d2[i]);
//        }
//
//        pU[0] = 0;
//        for (int32_t u = 0; u < n1; u++) {
//            pU[u + 1] = d1[u] + pU[u];
//        }
//        for (int32_t i = 0; i < m; i++) {
//            e1[pU[edges[i].u]++] = edges[i].v;
//        }
//        pU[0] = 0;
//        for (int32_t u = 0; u < n1; u++) {
//            pU[u + 1] = d1[u] + pU[u];
//        }
//
//        pV[0] = 0;
//        for (int32_t v = 0; v < n2; v++) {
//            pV[v + 1] = d2[v] + pV[v];
//        }
//        for (int32_t i = 0; i < m; i++) {
//            e2[pV[edges[i].v]++] = edges[i].u;
//        }
//        pV[0] = 0;
//        for (int32_t v = 0; v < n2; v++) {
//            pV[v + 1] = d2[v] + pV[v];
//        }
//
//        Heap_t l_heap(n1, maxDu + 1), r_heap(n2, maxDv + 1);
//        int32_t n = std::max(n1, n2);
//        std::vector <int32_t> ids(n);
//        std::vector <int32_t> keys(n);
//        std::vector <int32_t> labelsL(n1);
//        std::vector <int32_t> labelsR(n2);
//
//        for (int32_t i = 0; i < n1; i++) {
//            ids[i] = i;
//            keys[i] = d1[i] + 1;
//        }
//        l_heap.init(n1, maxDu + 1, ids.data(), keys.data());
//
//        for (int32_t i = 0; i < n2; i++) {
//            ids[i] = i;
//            keys[i] = d2[i] + 1;
//        }
//        r_heap.init(n2, maxDv + 1, ids.data(), keys.data());
//
//        int32_t minN = std::min(n1, n2);
//
//        for (int32_t i = 0; i < minN; i++) {
//            int32_t u, degU;
//            int32_t v, degV;
//
//            if (!l_heap.pop_min(u, degU)) printf("error l_heap\n");
//            if (!r_heap.pop_min(v, degV)) printf("error r_heap\n");
//
//            labelsL[u] = i;
//            labelsR[v] = i;
//            for (int32_t j = pU[u]; j < pU[u + 1]; j++) r_heap.decrement(e1[j]);
//
//            for (int32_t j = pV[v]; j < pV[v + 1]; j++) l_heap.decrement(e2[j]);
//
//        }
//        if (n1 < n2) {
//            for (int32_t j = n1; j < n2; j++) {
//                int32_t v, degV;
//                if (!r_heap.pop_min(v, degV)) printf("error r_heap\n");
//                labelsR[v] = j;
//            }
//        }
//        else {
//            for (int32_t j = n2; j < n1; j++) {
//                int32_t u, degU;
//                if (!l_heap.pop_min(u, degU)) printf("error l_heap\n");
//                labelsL[u] = j;
//            }
//        }
//
//        for (int32_t i = 0; i < m; i++) {
//            edges[i].u = labelsL[edges[i].u];
//            edges[i].v = labelsR[edges[i].v];
//        }
//
//        std::fill(d1.begin(), d1.begin() + n1, 0);
//        std::fill(d2.begin(), d2.begin() + n2, 0);
//        std::fill(pU.begin(), pU.begin() + n1 + 1, 0);
//        std::fill(pV.begin(), pV.begin() + n2 + 1, 0);
//
//        for (int32_t i = 0; i < m; i++) {
//            ++d1[edges[i].u];
//            ++d2[edges[i].v];
//        }
//
//        for (int32_t i = 0; i < n1; i++) {
//            pU[i + 1] = pU[i] + d1[i];
//        }
//        for (int32_t i = 0; i < n2; i++) {
//            pV[i + 1] = pV[i] + d2[i];
//        }
//
//        for (int32_t i = 0; i < m; i++) {
//            e1[pU[edges[i].u]++] = edges[i].v;
//        }
//        for (int32_t i = 0; i < m; i++) {
//            e2[pV[edges[i].v]++] = edges[i].u;
//        }
//
//        pU[0] = pV[0] = 0;
//        for (int32_t i = 0; i < n1; i++) {
//            pU[i + 1] = pU[i] + d1[i];
//        }
//        for (int32_t i = 0; i < n2; i++) {
//            pV[i + 1] = pV[i] + d2[i];
//        }
//
//        for (int32_t i = 0; i < n1; i++) {
//            std::sort(e1.begin() + pU[i], e1.begin() + pU[i + 1]);
//        }
//        for (int32_t i = 0; i < n2; i++) {
//            std::sort(e2.begin() + pV[i], e2.begin() + pV[i + 1]);
//        }
//    }

    void rawOrder() {
        std::vector <int32_t> d1, d2;

        d1.resize(n1);
        d2.resize(n2);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        maxDu = 0;
        for (int32_t i = 0; i < n1; i++) {
            maxDu = std::max(maxDu, d1[i]);
        }
        maxDv = 0;
        for (int32_t i = 0; i < n2; i++) {
            maxDv = std::max(maxDv, d2[i]);
        }

        pU[0] = 0;
        for (int32_t u = 0; u < n1; u++) {
            pU[u + 1] = d1[u] + pU[u];
        }
        for (int32_t i = 0; i < m; i++) {
            e1[pU[edges[i].u]++] = edges[i].v;
        }
        pU[0] = 0;
        for (int32_t u = 0; u < n1; u++) {
            pU[u + 1] = d1[u] + pU[u];
        }

        pV[0] = 0;
        for (int32_t v = 0; v < n2; v++) {
            pV[v + 1] = d2[v] + pV[v];
        }
        for (int32_t i = 0; i < m; i++) {
            e2[pV[edges[i].v]++] = edges[i].u;
        }
        pV[0] = 0;
        for (int32_t v = 0; v < n2; v++) {
            pV[v + 1] = d2[v] + pV[v];
        }

        for (int32_t i = 0; i < n1; i++) {
            std::sort(e1.begin() + pU[i], e1.begin() + pU[i + 1]);
        }
        for (int32_t i = 0; i < n2; i++) {
            std::sort(e2.begin() + pV[i], e2.begin() + pV[i + 1]);
        }
    }

    void changeToDegreeOrder() {
        std::vector <int32_t> d1, d2;
        std::vector <int32_t> label1, label2;

        d1.resize(std::max(n1, n2) + 1);
        d2.resize(std::max(n1, n2) + 1);
        label1.resize(n1);
        label2.resize(n2);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        maxDu = 0;
        for (int32_t i = 0; i < n1; i++) {
            maxDu = std::max(maxDu, d1[i]);
        }

        maxDv = 0;
        for (int32_t i = 0; i < n2; i++) {
            maxDv = std::max(maxDv, d2[i]);
        }

        for (int32_t i = 0; i < n1; i++) {
            pV[d1[i] + 1]++;
        }
        for (int32_t i = 0; i < maxDu; i++) {
            pV[i + 1] += pV[i];
        }
        for (int32_t i = 0; i < n1; i++) {
            label1[i] = pV[d1[i]]++;
        }
        for (int32_t i = 0; i < n2; i++) {
            pU[d2[i] + 1]++;
        }
        for (int32_t i = 0; i < maxDv; i++) {
            pU[i + 1] += pU[i];
        }

        for (int32_t i = 0; i < n2; i++) {
            label2[i] = pU[d2[i]]++;
        }

        for (int32_t i = 0; i < m; i++) {
            edges[i].u = label1[edges[i].u];
            edges[i].v = label2[edges[i].v];
        }

        std::fill(d1.begin(), d1.begin() + std::max(n1, n2) + 1, 0);
        std::fill(d2.begin(), d2.begin() + std::max(n1, n2) + 1, 0);
        std::fill(pU.begin(), pU.begin() + n1 + 1, 0);
        std::fill(pV.begin(), pV.begin() + n2 + 1, 0);

        for (int32_t i = 0; i < m; i++) {
            ++d1[edges[i].u];
            ++d2[edges[i].v];
        }

        for (int32_t i = 0; i < n1; i++) {
            pU[i + 1] = pU[i] + d1[i];
        }
        for (int32_t i = 0; i < n2; i++) {
            pV[i + 1] = pV[i] + d2[i];
        }

        for (int32_t i = 0; i < m; i++) {
            e1[pU[edges[i].u]++] = edges[i].v;
        }
        for (int32_t i = 0; i < m; i++) {
            e2[pV[edges[i].v]++] = edges[i].u;
        }
        pU[0] = pV[0] = 0;
        for (int32_t i = 0; i < n1; i++) {
            pU[i + 1] = pU[i] + d1[i];
        }
        for (int32_t i = 0; i < n2; i++) {
            pV[i + 1] = pV[i] + d2[i];
        }

        for (int32_t i = 0; i < n1; i++) {
            std::sort(e1.begin() + pU[i], e1.begin() + pU[i + 1]);
        }
        for (int32_t i = 0; i < n2; i++) {
            std::sort(e2.begin() + pV[i], e2.begin() + pV[i + 1]);
        }
    }

    void swapUV() {
        std::swap(n[0], n[1]);
        std::swap(maxDu, maxDv);

        p[0].swap(p[1]);
        e[0].swap(e[1]);
    }

    int32_t deg1(int32_t u) {
        return p[0][u + 1] - p[0][u];
    }

    int32_t deg2(int32_t v) {
        return p[1][v + 1] - p[1][v];
    }

#if defined(IPS_ST_V15_ROW_CACHE) && !defined(IPS_DISABLE_ST)
    // State-local adjacency probe. Bitmap address is resolved once per outer
    // vertex instead of reloading bitOffset for every opposite-side candidate.
    // No persistent memory is allocated for this object.
    struct RowProbe {
        const uint64_t *bits;
        CuckooHash *hash;
#ifdef IPS_PREFIX_SHARE
        const uint64_t *prefixBits;
        const int32_t *prefixPositions;
#endif
        inline bool contains(int32_t v) const {
            if (bits != nullptr)
                return (bits[static_cast<uint32_t>(v) >> 6] >> (v & 63)) & 1ULL;
#ifdef IPS_PREFIX_SHARE
            if(prefixBits!=nullptr){
                const int32_t at=prefixPositions[v];
                if(at>=0)return (prefixBits[at>>6]>>(at&63))&1ULL;
            }
#endif
            return hash->find(v);
        }
    };

    inline RowProbe rowProbe(int32_t u, int32_t t) {
        const int64_t off = bitOffset[t][u];
#ifdef IPS_PREFIX_SHARE
        const uint64_t *prefix=(off<0)?getPrefixRow(u,t):nullptr;
        return RowProbe{off >= 0 ? bitData[t].data() + off : nullptr,
                        &cuhash[t][u], prefix, prefixPositions.data()};
#else
        return RowProbe{off >= 0 ? bitData[t].data() + off : nullptr,
                        &cuhash[t][u]};
#endif
    }
#endif

    inline bool connect(int32_t u, int32_t v, int32_t t) {
#ifndef IPS_DISABLE_ST
        int64_t off = bitOffset[t][u];
        if (off >= 0) return (bitData[t][off + (v >> 6)] >> (v & 63)) & 1ULL;
#endif
        return cuhash[t][u].find(v);
    }

    void print() {
        printf("U:\n");
        for (int32_t u = 0; u < n[0]; u++) {
            printf("%u:", u);
            for (int32_t i = p[0][u]; i < p[0][u + 1]; i++) {
                printf("%u ", e[0][i]);
            }
            printf("\n");
        }
        printf("V:\n");
        for (int32_t v = 0; v < n[1]; v++) {
            printf("%u:", v);
            for (int32_t i = p[1][v]; i < p[1][v + 1]; i++) {
                printf("%u ", e[1][i]);
            }
            printf("\n");
        }
    }

    int32_t deg(int32_t u, int32_t t) {
        return p[t][u + 1] - p[t][u];
    }

};

//class Stat_t {
//private:
//    struct rusage s{};
//    struct rusage t{};
//
//public:
//    double runtime = 0;
//
//    Stat_t() = default;
//
//    void setup() {
//        if (getrusage(RUSAGE_THREAD, &s) != 0) {
//            fprintf(stderr, "The running time info couldn't be collected successfully.\n");
//            exit(0);
//        }
//    }
//    void collapse() {
//        if (getrusage(RUSAGE_THREAD, &t) != 0) {
//            fprintf(stderr, "The running time info couldn't be collected successfully.\n");
//            exit(0);
//        }
//
//        this->runtime =  ((float)(t.ru_utime.tv_sec - s.ru_utime.tv_sec)) * 1e3 +
//                         ((float)(t.ru_utime.tv_usec - s.ru_utime.tv_usec)) * 1e-3;      // ms
//    }
//};

#endif