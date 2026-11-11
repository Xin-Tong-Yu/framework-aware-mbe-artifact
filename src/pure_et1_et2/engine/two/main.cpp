#include "args.hpp"
#include "ips.hpp"
#include "graph.hpp"
#include <string>
#include <chrono>
#include <iostream>
#include <fstream>
#include <string>

int main(int argc, char* argv[]) {
    argsController ac(argc, argv);

    if (ac.exist("-c")) {
        printf("Pre-process %s\n", argv[2]);
        std::string src_filename(argv[2]);
        std::string suffix = src_filename.substr(src_filename.find_last_of('.'));
        if (suffix != ".edges" && suffix != ".mtx") return 0;
        std::string prefix = src_filename.substr(0, src_filename.find_last_of('.'));
        std::string clean_filename = prefix + ".clean";
        clean_edges(src_filename.c_str(), clean_filename.c_str());

        return 0;
    }

    if (ac.exist("-gv")) {
        int p = std::stoi(ac["-p"]);
        std::string src_filename = ac["-gv"];

        printf("Generate (v) from %s, prob = %.2lf\n", src_filename.c_str(), (double) p / 100.);

        std::string suffix = src_filename.substr(src_filename.find_last_of('.'));
        if (suffix != ".clean") return 0;
        std::string prefix = src_filename.substr(0, src_filename.find_last_of('.'));
        std::string gen_filename = prefix + ".gv" + ac["-p"];

        gen_vertex(src_filename.c_str(), gen_filename.c_str(), (double) p / 100.);

        return 0;
    }

    if (ac.exist("-gp")) {
        int n = std::stoi(ac["-n"]);
        std::string filename = ac["-gp"];

        gen_plex(filename.c_str(), n);
        return 0;
    }

    if (ac.exist("-ge")) {
        int p = std::stoi(ac["-p"]);
        std::string src_filename = ac["-ge"];

        printf("Generate (e) from %s, prob = %.2lf\n", src_filename.c_str(), (double) p / 100.);

        std::string suffix = src_filename.substr(src_filename.find_last_of('.'));
        if (suffix != ".clean") return 0;
        std::string prefix = src_filename.substr(0, src_filename.find_last_of('.'));
        std::string gen_filename = prefix + ".ge" + ac["-p"];

        gen_edge(src_filename.c_str(), gen_filename.c_str(), (double) p / 100.);

        return 0;
    }

    if (!ac.exist("-f")) {
        printf("file path: -f\n");
        return 0;
    }

    if (!ac.exist("-d")) {
        printf("graph order: -d(core, two, raw)\n");
        return 0;
    }

    int32_t ls = 1, rs = 1;
    if (ac.exist("-l")) ls = std::stoi(ac["-l"]);
    if (ac.exist("-r")) rs = std::stoi(ac["-r"]);

    std::string fPath = ac["-f"];
    std::string order = ac["-d"];


    printf("Algorithm: Two-Modular-Enum\n");
    IPS_t ips(fPath, order, ls, rs);
    if (ac.exist("-o") && !ips.enableOutput(ac["-o"])) {
        std::cerr << "Cannot open output file: " << ac["-o"] << std::endl;
        return 1;
    }
    ips.run();


    std::ifstream status("/proc/self/status");
    for (std::string line; std::getline(status, line);) {
        if (line.rfind("VmPeak:", 0) == 0) {
            std::cout << "[MEMORY] VmPeak: " << std::stod(line.substr(7)) / 1024.0 << "MB" << std::endl;
        }
        if (line.rfind("VmSize:", 0) == 0) {
            std::cout << "[MEMORY] VmSize: " << std::stod(line.substr(7)) / 1024.0 << "MB" << std::endl;
        }
        if (line.rfind("VmHWM:", 0) == 0) {
            std::cout << "[MEMORY] VmHWM: " << std::stod(line.substr(6)) / 1024.0 << "MB" << std::endl;
        }
        if (line.rfind("VmRSS:", 0) == 0) {
            std::cout << "[MEMORY] VmRSS: " << std::stod(line.substr(6)) / 1024.0 << "MB" << std::endl << std::endl;
        }
    }


    return 0;
}